"""Brokerage activity import: a broker's history file into one account, sorted as it comes in.

Every row becomes a transaction (``source = "csv"``, duplicates skipped the same way as a bank
file: ``csv_parsing.fingerprint``). Then, in one database transaction:

- buys and sells with a symbol and shares become stock purchases and sales linked to their
  transaction (like **Stock trade** on the Transactions page), matched with FIFO;
- the rest is sorted like a bank import: auto-sort rules, dividends and their sweeps, transfers.

A sale that needs more shares than the account held stops the whole import (422). Reading the
file is in ``activity_csv``. Nothing here logs file contents, descriptions or amounts.
"""

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import (
    StockLot,
    StockSaleOrder,
    Transaction,
    TransactionKind,
    TransactionSource,
)
from app.schemas.activity_import import (
    ActivityChoices,
    ActivityColumns,
    ActivityPreview,
    ActivityPreviewRow,
    ActivityResult,
)
from app.schemas.stocks import LotCreate
from app.services import stock_gains as gains
from app.services.accounts import INVESTMENT_KINDS, get_account
from app.services.activity_csv import ActivityRow, find_columns, parse_row
from app.services.category_rules import load_matcher, rule_fields
from app.services.csv_parsing import (
    RowProblem,
    decode_csv,
    detect_delimiter,
    fingerprint,
    read_rows,
)
from app.services.dividend_matching import find_dividends
from app.services.imports import record
from app.services.stock_records import rematch
from app.services.transfer_matching import match_transfers
from app.shares import micro_to_text

PREVIEW_ROWS = 50
MAX_PROBLEM_ROWS = 100


@dataclass
class _Prepared:
    columns: ActivityColumns
    rows: list[tuple[ActivityPreviewRow, ActivityRow | None, str | None]]  # with fingerprints


def _trade_text(r: ActivityRow) -> str | None:
    if r.trade is None:
        return None
    verb = "Buy" if r.kind == "buy" else "Sell"
    return f"{verb} {micro_to_text(r.trade.shares_micro)} {r.trade.symbol}"


def _prepare(session: Session, account_id: int, data: bytes) -> _Prepared:
    account = get_account(session, account_id)
    if account.kind not in INVESTMENT_KINDS:
        raise ApiError(
            422,
            "not_an_investment_account",
            "Brokerage activity goes in a brokerage, retirement or HSA account. Use Import bank "
            "file for checking, savings and cards.",
        )
    text = decode_csv(data)
    rows = read_rows(text, detect_delimiter(text))
    header, columns = find_columns(rows)
    seen: Counter = Counter()
    parsed = []
    for number, row in enumerate(rows[header + 1 :], start=header + 2):
        if not any(c.strip() for c in row):
            continue
        try:
            r = parse_row(row, number, columns, account_id)
        except RowProblem as problem:
            out = ActivityPreviewRow(row_number=number, status="invalid", problem=str(problem))
            parsed.append((out, None, None))
            continue
        key = (r.date, r.amount_cents, r.description.casefold())
        fp = fingerprint(account_id, r.date, r.amount_cents, r.description, seen[key])
        seen[key] += 1
        out = ActivityPreviewRow(
            row_number=number,
            date=r.date,
            description=r.description,
            amount_cents=r.amount_cents,
            trade=_trade_text(r),
        )
        parsed.append((out, r, fp))
    fps = [fp for _, _, fp in parsed if fp]
    if fps:
        existing = set(
            session.scalars(
                select(Transaction.import_fingerprint).where(
                    Transaction.import_fingerprint.in_(fps)
                )
            )
        )
        for out, _, fp in parsed:
            if fp in existing:
                out.status = "duplicate"
    return _Prepared(columns, parsed)


def preview(session: Session, account_id: int, data: bytes) -> ActivityPreview:
    p = _prepare(session, account_id, data)
    rows = [out for out, _, _ in p.rows]
    counts = Counter(r.status for r in rows)
    problems = [r for r in rows[PREVIEW_ROWS:] if r.status == "invalid"][:MAX_PROBLEM_ROWS]
    return ActivityPreview(
        columns=p.columns,
        total_rows=len(rows),
        new_rows=counts["new"],
        new_trades=sum(r.status == "new" and r.trade is not None for r in rows),
        duplicate_rows=counts["duplicate"],
        invalid_rows=counts["invalid"],
        rows=rows[:PREVIEW_ROWS] + problems,
    )


def _add_trades(session: Session, added: list[tuple[Transaction, ActivityRow]], import_id: int):
    trades = [(t, r) for t, r in added if r.trade is not None]
    for transaction, r in trades:
        if isinstance(r.trade, LotCreate):
            row = StockLot(**r.trade.model_dump(exclude={"shares", "cost_basis"}))
        else:
            row = StockSaleOrder(**r.trade.model_dump(exclude={"shares", "proceeds"}))
        row.transaction_id, row.import_id = transaction.id, import_id
        session.add(row)
    session.flush()
    try:
        for symbol in sorted({r.trade.symbol for _, r in trades}):
            rematch(session, symbol, added[0][0].account_id)
    except gains.NotEnoughShares as exc:
        session.rollback()
        raise ApiError(
            422,
            "not_enough_shares",
            f"The sale of {exc.sale.symbol} on {exc.sale.sold_on.isoformat()} is for more shares "
            "than this account held then. Import the file that has the earlier purchases first, "
            "or add them on the Stocks page. Nothing was imported.",
        ) from None
    return len(trades)


def commit(
    session: Session, account_id: int, data: bytes, choices: ActivityChoices
) -> ActivityResult:
    """All of it, or none."""
    p = _prepare(session, account_id, data)
    invalid = [out.row_number for out, _, _ in p.rows if out.status == "invalid"]
    if invalid and not choices.skip_invalid_rows:
        listed = ", ".join(str(n) for n in invalid[:10]) + (", ..." if len(invalid) > 10 else "")
        raise ApiError(
            422,
            "invalid_rows",
            f"{len(invalid)} row(s) couldn't be read (row {listed}). Fix them in the file, or "
            "choose to skip those rows.",
        )
    new = [(r, fp) for out, r, fp in p.rows if out.status == "new"]
    if not new:
        return ActivityResult(
            imported=0,
            trades=0,
            dividends_found=0,
            categorized=0,
            transfers_matched=0,
            skipped_duplicates=sum(out.status == "duplicate" for out, _, _ in p.rows),
            skipped_invalid=len(invalid),
        )
    import_id = record(session, "activity", account_id, choices.file_name, len(new))
    match = load_matcher(session)
    added = []
    for r, fp in new:
        transaction = Transaction(
            account_id=account_id,
            date=r.date,
            amount_cents=r.amount_cents,
            description=r.description,
            # A trade needs no category: it's left out of the budget.
            **(rule_fields(match(r.description)) if r.trade is None else {}),
            source=TransactionSource.CSV,
            kind=TransactionKind.NORMAL,
            import_fingerprint=fp,
            import_id=import_id,
        )
        session.add(transaction)
        added.append((transaction, r))
    session.flush()
    trades = _add_trades(session, added, import_id)
    ids = {t.id for t, _ in added}
    dividends = find_dividends(session, ids)
    matched = match_transfers(session, ids)
    session.commit()
    return ActivityResult(
        imported=len(added),
        trades=trades,
        dividends_found=dividends.dividends,
        categorized=sum(t.category_id is not None for t, _ in added),
        transfers_matched=matched,
        skipped_duplicates=sum(out.status == "duplicate" for out, _, _ in p.rows),
        skipped_invalid=len(invalid),
    )
