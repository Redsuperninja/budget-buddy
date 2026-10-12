"""Bank CSV import: prepare the file, preview the rows, then add them.

Imported rows are ordinary ("normal") transactions with ``source = "csv"``, put in a category by
the auto-categorization rules where one matches (``category_rules``). Transfers aren't detected
here; link them afterwards. Reading the file is in ``csv_parsing`` and column guessing
in ``csv_columns``. Nothing here logs file contents, descriptions or amounts.
"""

from collections import Counter
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import (
    AccountKind,
    CsvImportMapping,
    Transaction,
    TransactionKind,
    TransactionSource,
)
from app.schemas.imports.csv_import import (
    CommitChoices,
    CsvMapping,
    ImportPreview,
    ImportResult,
    MappingChoices,
    PreviewRow,
)
from app.services.budget.category_rules import load_matcher, rule_fields
from app.services.imports.card_signs import FLIPPED, looks_flipped
from app.services.imports.csv_columns import build_mapping, columns_used, detect_columns
from app.services.imports.csv_parsing import (
    RowProblem,
    decode_csv,
    detect_delimiter,
    fingerprint,
    parse_row,
    read_rows,
)
from app.services.imports.history import record
from app.services.investing.bank_trades import find_trades
from app.services.investing.dividend_matching import find_dividends
from app.services.ledger.accounts import get_account
from app.services.ledger.transfer_matching import match_transfers
from app.services.repeat_gifts import repeat_gifts

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
PREVIEW_ROWS = 50
MAX_PROBLEM_ROWS = 100
SAMPLE_ROWS = 5
NEED_COLUMNS = (
    "We couldn't tell which columns hold the date, the description and the amount. "
    "Please choose them."
)


@dataclass
class _Prepared:
    mapping: CsvMapping | None
    used_saved: bool
    columns: list[str]
    sample: list[list[str]]
    rows: list[tuple[PreviewRow, str | None]]  # each row with its fingerprint
    flipped: bool = False  # a card file read the other way round (card_signs)


def _saved_mapping(session: Session, account_id: int) -> CsvMapping | None:
    saved = session.get(CsvImportMapping, account_id)
    if saved is None:
        return None
    try:
        return CsvMapping.model_validate_json(saved.mapping)
    except ValidationError:  # saved by an older version that no longer fits
        return None


def _prepare(session: Session, account_id: int, data: bytes, choices: MappingChoices) -> _Prepared:
    account = get_account(session, account_id)
    text = decode_csv(data)
    delimiter = choices.delimiter or detect_delimiter(text)
    rows = read_rows(text, delimiter)
    width = max(len(r) for r in rows)

    saved = _saved_mapping(session, account_id)
    used_saved = (
        saved is not None and saved.delimiter == delimiter and max(columns_used(saved)) < width
    )
    base = saved.model_dump() if used_saved else {**detect_columns(rows), "delimiter": delimiter}
    mapping = build_mapping(base, choices, rows)
    if mapping is not None and max(columns_used(mapping)) >= width:
        raise ApiError(
            422,
            "invalid_mapping",
            f"This file only has {width} columns, numbered 0 to {width - 1}.",
        )

    header_rows = mapping.header_rows if mapping else base.get("header_rows", 0)
    names = rows[header_rows - 1] if 0 < header_rows <= len(rows) else []
    columns = [
        (names[i].strip()[:100] if i < len(names) else "") or f"Column {i + 1}"
        for i in range(width)
    ]
    sample = [r for r in rows[header_rows:] if any(c.strip() for c in r)][:SAMPLE_ROWS]
    parsed = _parse_rows(session, account_id, rows, mapping) if mapping else []
    flipped = (
        mapping is not None
        and account.kind == AccountKind.CREDIT_CARD
        and choices.flip_sign is None
        and looks_flipped([(r.description, r.amount_cents) for r, _ in parsed if r.date])
    )
    if flipped:
        mapping = mapping.model_copy(update={"flip_sign": not mapping.flip_sign})
        parsed = _parse_rows(session, account_id, rows, mapping)
    used = used_saved and mapping is not None
    return _Prepared(mapping, used, columns, sample, parsed, flipped)


def _parse_rows(
    session: Session, account_id: int, rows: list[list[str]], mapping: CsvMapping
) -> list[tuple[PreviewRow, str | None]]:
    seen: Counter = Counter()
    parsed: list[tuple[PreviewRow, str | None]] = []
    for number, row in enumerate(rows[mapping.header_rows :], start=mapping.header_rows + 1):
        if not any(c.strip() for c in row):
            continue
        try:
            date, description, cents = parse_row(row, mapping)
        except RowProblem as problem:
            out = PreviewRow(row_number=number, status="invalid", problem=str(problem))
            parsed.append((out, None))
            continue
        key = (date, cents, description.casefold())
        fp = fingerprint(account_id, date, cents, description, seen[key])
        seen[key] += 1
        out = PreviewRow(row_number=number, date=date, description=description, amount_cents=cents)
        parsed.append((out, fp))

    dates = [r.date for r, _ in parsed if r.date is not None]
    if dates:
        existing = set(
            session.scalars(
                select(Transaction.import_fingerprint).where(
                    Transaction.account_id == account_id,
                    Transaction.import_fingerprint.is_not(None),
                    Transaction.date.between(min(dates), max(dates)),
                )
            )
        )
        for out, fp in parsed:
            if fp in existing:
                out.status = "duplicate"
    return parsed


def preview(session: Session, account_id: int, data: bytes, choices: MappingChoices):
    p = _prepare(session, account_id, data, choices)
    rows = [r for r, _ in p.rows]
    counts = Counter(r.status for r in rows)
    problems = [r for r in rows[PREVIEW_ROWS:] if r.status == "invalid"][:MAX_PROBLEM_ROWS]
    return ImportPreview(
        mapping=p.mapping,
        used_saved_mapping=p.used_saved,
        message=FLIPPED if p.flipped else None if p.mapping else NEED_COLUMNS,
        columns=p.columns,
        sample=p.sample,
        total_rows=len(rows),
        new_rows=counts["new"],
        duplicate_rows=counts["duplicate"],
        invalid_rows=counts["invalid"],
        rows=rows[:PREVIEW_ROWS] + problems,
    )


def commit(session: Session, account_id: int, data: bytes, choices: CommitChoices):
    """Add every new row in one database transaction: all of them, or none."""
    p = _prepare(session, account_id, data, choices)
    if p.mapping is None:
        raise ApiError(422, "mapping_needed", NEED_COLUMNS)
    invalid = [r.row_number for r, _ in p.rows if r.status == "invalid"]
    if invalid and not choices.skip_invalid_rows:
        listed = ", ".join(str(n) for n in invalid[:10]) + (", ..." if len(invalid) > 10 else "")
        raise ApiError(
            422,
            "invalid_rows",
            f"{len(invalid)} rows couldn't be read (row {listed}). Check the column choices, "
            "or choose to skip those rows.",
        )
    new = [(r, fp) for r, fp in p.rows if r.status == "new"]
    import_id = record(session, "bank", account_id, choices.file_name, len(new)) if new else None
    match = load_matcher(session)
    added = [
        Transaction(
            account_id=account_id,
            date=r.date,
            amount_cents=r.amount_cents,
            description=r.description,
            **rule_fields(match(r.description)),
            source=TransactionSource.CSV,
            kind=TransactionKind.NORMAL,
            import_fingerprint=fp,
            import_id=import_id,
        )
        for r, fp in new
    ]
    session.add_all(added)
    if choices.save_mapping:
        saved = session.get(CsvImportMapping, account_id) or CsvImportMapping(account_id=account_id)
        saved.mapping = p.mapping.model_dump_json()
        session.add(saved)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiError(
            409,
            "import_conflict",
            "Some of these rows were imported at the same time by another window. "
            "Please preview the file again.",
        ) from None
    # Dividends and their deposit sweeps first, then card payments and moves between your
    # accounts in this file, matched with the other side.
    dividends = find_dividends(session, {t.id for t in added})
    trades = find_trades(session, {t.id for t in added})  # stock trades and their sweeps
    matched = match_transfers(session, {t.id for t in added})
    gifts = repeat_gifts(session, {t.id for t in added})  # monthly giving to a charity you gave to
    session.commit()
    return ImportResult(
        imported=len(new),
        transfers_matched=matched,
        dividends_found=dividends.dividends,
        dividend_sweeps_linked=dividends.sweeps,
        donations_added=gifts.recorded,
        trades_found=trades.trades,
        trade_sweeps_linked=trades.sweeps,
        categorized=sum(t.category_id is not None for t in added),
        skipped_duplicates=sum(r.status == "duplicate" for r, _ in p.rows),
        skipped_invalid=len(invalid),
        mapping_saved=choices.save_mapping,
    )


def forget_mapping(session: Session, account_id: int) -> None:
    get_account(session, account_id)
    saved = session.get(CsvImportMapping, account_id)
    if saved is not None:
        session.delete(saved)
        session.commit()
