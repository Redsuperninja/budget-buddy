"""Stock CSV import: preview the rows, then add the purchases and sales in one go.

Reading the file is in ``stock_csv``. Duplicates: a row is skipped when the same purchase or sale
(type, symbol, date, shares and money) is already in the account. Identical rows are counted, so
importing the same file twice adds nothing, but two real identical purchases in one file are both
kept. Sales use FIFO like hand-entered ones (``stock_records.rematch``). Nothing here logs file
contents, symbols or amounts.
"""

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import StockLot, StockSaleOrder
from app.schemas.stock_import import (
    StockColumns,
    StockCommitChoices,
    StockImportChoices,
    StockImportPreview,
    StockImportResult,
    StockPreviewRow,
)
from app.schemas.stocks import LotCreate
from app.services import stock_gains as gains
from app.services.csv_parsing import RowProblem, decode_csv, detect_delimiter, read_rows
from app.services.stock_csv import ParsedRow, find_columns, parse_row
from app.services.stock_records import check_account, in_account, rematch
from app.shares import micro_to_text

PREVIEW_ROWS = 50
MAX_PROBLEM_ROWS = 100


@dataclass
class _Prepared:
    columns: StockColumns
    rows: list[tuple[StockPreviewRow, ParsedRow | None]]


def _key(kind: str, symbol: str, date, shares_micro: int, cents: int) -> tuple:
    return kind, symbol, date, shares_micro, cents


def _row_key(p: ParsedRow) -> tuple:
    t = p.trade
    if isinstance(t, LotCreate):
        return _key("buy", t.symbol, t.acquired_on, t.shares_micro, t.cost_basis_cents)
    return _key("sell", t.symbol, t.sold_on, t.shares_micro, t.proceeds_cents)


def _existing(session: Session, account_id: int | None, symbols: set[str]) -> Counter:
    lots = session.scalars(
        select(StockLot).where(
            StockLot.symbol.in_(symbols), in_account(StockLot.account_id, account_id)
        )
    )
    orders = session.scalars(
        select(StockSaleOrder).where(
            StockSaleOrder.symbol.in_(symbols), in_account(StockSaleOrder.account_id, account_id)
        )
    )
    return Counter(
        [_key("buy", r.symbol, r.acquired_on, r.shares_micro, r.cost_basis_cents) for r in lots]
        + [_key("sell", r.symbol, r.sold_on, r.shares_micro, r.proceeds_cents) for r in orders]
    )


def _out(p: ParsedRow) -> StockPreviewRow:
    t = p.trade
    is_buy = isinstance(t, LotCreate)
    return StockPreviewRow(
        row_number=p.row_number,
        kind=p.kind,
        symbol=t.symbol,
        date=t.acquired_on if is_buy else t.sold_on,
        shares=micro_to_text(t.shares_micro),
        money_cents=t.cost_basis_cents if is_buy else t.proceeds_cents,
    )


def _prepare(session: Session, data: bytes, choices: StockImportChoices) -> _Prepared:
    check_account(session, choices.account_id)
    text = decode_csv(data)
    rows = read_rows(text, detect_delimiter(text))
    header, columns = find_columns(rows)
    parsed: list[tuple[StockPreviewRow, ParsedRow | None]] = []
    for number, row in enumerate(rows[header + 1 :], start=header + 2):
        if not any(c.strip() for c in row):
            continue
        try:
            p = parse_row(row, number, columns, choices.account_id)
        except RowProblem as problem:
            parsed.append(
                (StockPreviewRow(row_number=number, status="invalid", problem=str(problem)), None)
            )
            continue
        parsed.append((_out(p), p))

    symbols = {p.trade.symbol for _, p in parsed if p is not None}
    existing = _existing(session, choices.account_id, symbols) if symbols else Counter()
    for out, p in parsed:
        if p is not None and existing[_row_key(p)] > 0:
            existing[_row_key(p)] -= 1
            out.status = "duplicate"
    return _Prepared(columns, parsed)


def preview(session: Session, data: bytes, choices: StockImportChoices) -> StockImportPreview:
    p = _prepare(session, data, choices)
    rows = [r for r, _ in p.rows]
    counts = Counter(r.status for r in rows)
    new = Counter(r.kind for r in rows if r.status == "new")
    problems = [r for r in rows[PREVIEW_ROWS:] if r.status == "invalid"][:MAX_PROBLEM_ROWS]
    return StockImportPreview(
        columns=p.columns,
        total_rows=len(rows),
        new_buys=new["buy"],
        new_sells=new["sell"],
        duplicate_rows=counts["duplicate"],
        invalid_rows=counts["invalid"],
        rows=rows[:PREVIEW_ROWS] + problems,
    )


def _not_enough(exc: gains.NotEnoughShares) -> ApiError:
    sale = exc.sale
    return ApiError(
        422,
        "not_enough_shares",
        f"The sale of {sale.symbol} on {sale.sold_on.isoformat()} is for more shares than you "
        "owned then in this account. Only purchases in the same account, dated on or before the "
        "sale, count. Add the missing purchases to the file (or enter them first), then import "
        "again. Nothing was imported.",
    )


def commit(session: Session, data: bytes, choices: StockCommitChoices) -> StockImportResult:
    """Add every new row in one database transaction: all of them, or none."""
    p = _prepare(session, data, choices)
    invalid = [r.row_number for r, _ in p.rows if r.status == "invalid"]
    if invalid and not choices.skip_invalid_rows:
        listed = ", ".join(str(n) for n in invalid[:10]) + (", ..." if len(invalid) > 10 else "")
        raise ApiError(
            422,
            "invalid_rows",
            f"{len(invalid)} row(s) couldn't be read (row {listed}). Fix them in the file, or "
            "choose to skip those rows.",
        )
    new = [parsed for out, parsed in p.rows if out.status == "new"]
    for parsed in new:
        t = parsed.trade
        if isinstance(t, LotCreate):
            session.add(StockLot(**t.model_dump(exclude={"shares", "cost_basis"})))
        else:
            session.add(StockSaleOrder(**t.model_dump(exclude={"shares", "proceeds"})))
    session.flush()
    try:
        for symbol in sorted({parsed.trade.symbol for parsed in new}):
            rematch(session, symbol, choices.account_id)
    except gains.NotEnoughShares as exc:
        session.rollback()
        raise _not_enough(exc) from None
    session.commit()
    buys = sum(parsed.kind == "buy" for parsed in new)
    return StockImportResult(
        purchases_added=buys,
        sales_added=len(new) - buys,
        skipped_duplicates=sum(out.status == "duplicate" for out, _ in p.rows),
        skipped_invalid=len(invalid),
    )
