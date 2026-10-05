"""Bank CSV import: read the file, work out its columns, preview the rows, then add them.

Imported rows are ordinary ("normal") transactions with ``source = "csv"``. Transfers aren't
detected here; link them afterwards. Nothing in this module logs file contents, descriptions or
amounts, and error messages only ever name row numbers.

Duplicates: every imported row stores a fingerprint, a SHA-256 of (account, date, amount,
description in lower case, occurrence). "Occurrence" counts identical rows within the same file
(two $4.50 coffees at the same shop on the same day are 0 and 1), so a real repeat is kept but
importing an overlapping statement again skips the rows already there.
"""

import codecs
import csv
import datetime as dt
import hashlib
import io
import json
import re
from collections import Counter
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import CsvImportMapping, Transaction, TransactionKind, TransactionSource
from app.money import dollars_to_cents
from app.schemas.csv_import import (
    DATE_FORMATS,
    CommitChoices,
    CsvMapping,
    ImportPreview,
    ImportResult,
    MappingChoices,
    PreviewRow,
)
from app.services.accounts import get_account

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10_000
PREVIEW_ROWS = 50
MAX_PROBLEM_ROWS = 100
SAMPLE_ROWS = 5
MAX_DESCRIPTION = 500
# A spreadsheet treats a cell starting with one of these as a formula ("CSV injection").
FORMULA_STARTS = ("=", "+", "-", "@")
DELIMITERS = (",", ";", "\t", "|")
AMOUNT_COLUMNS = ("amount_column", "debit_column", "credit_column")

_THOUSANDS = re.compile(r"[0-9]{1,3}(,[0-9]{3})+(\.[0-9]+)?")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SPACES = re.compile(r"\s+")
# Words in column names, most specific first. Roles are matched in this order, and a column is
# used once, so "Debit Amount" becomes the money-out column, not the amount column.
_HEADER_WORDS = {
    "date_column": ("transaction date", "trans date", "date"),
    "debit_column": ("debit", "withdrawal", "money out", "paid out"),
    "credit_column": ("credit", "deposit", "money in", "paid in"),
    "amount_column": ("amount",),
    "description_column": ("description", "payee", "merchant", "details", "memo", "name"),
}
_MONEY_WORDS = tuple(w for role in AMOUNT_COLUMNS for w in _HEADER_WORDS[role])
NEED_COLUMNS = (
    "We couldn't tell which columns hold the date, the description and the amount. "
    "Please choose them."
)


class _RowProblem(Exception):
    pass


@dataclass
class _Prepared:
    mapping: CsvMapping | None
    used_saved: bool
    columns: list[str]
    sample: list[list[str]]
    rows: list[tuple[PreviewRow, str | None]]  # each row with its fingerprint


def decode_csv(data: bytes) -> str:
    """Bytes to text: UTF-16 or UTF-8 (with or without a byte-order mark), else Windows-1252."""
    try:
        if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            text = data.decode("utf-16")
        else:
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = data.decode("cp1252", errors="replace")
    except UnicodeDecodeError:
        text = "\x00"
    if "\x00" in text:
        raise ApiError(400, "not_a_csv", "This file doesn't look like a CSV file from your bank.")
    if not text.strip():
        raise ApiError(400, "empty_file", "This file is empty.")
    return text


def _detect_delimiter(text: str) -> str:
    """The separator that splits the first lines into the most columns (comma on a tie)."""
    lines = [line for line in text.splitlines()[:30] if line.strip()]
    best, best_count = ",", 1
    for delimiter in DELIMITERS:
        counts = Counter(len(row) for row in csv.reader(lines, delimiter=delimiter))
        count = counts.most_common(1)[0][0]
        if count > best_count:
            best, best_count = delimiter, count
    return best


def _read_rows(text: str, delimiter: str) -> list[list[str]]:
    rows = []
    try:
        for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter):
            if len(rows) >= MAX_ROWS + 20:  # a little room for header lines
                raise ApiError(
                    413,
                    "too_many_rows",
                    f"This file has more than {MAX_ROWS:,} rows. Please export a shorter date "
                    "range and import it in parts.",
                )
            rows.append(row)
    except csv.Error:
        raise ApiError(400, "unreadable_csv", "We couldn't read this CSV file.") from None
    return rows


def parse_amount(text: str) -> int | None:
    """A bank's amount text to cents: ``"$1,234.56"``, ``"(12.00)"``, ``"12.00-"``, ``"-5"``.

    Returns None for an empty cell. Raises ValueError for anything else it can't read exactly,
    including a comma that isn't a thousands separator (``"12,34"``), rather than guess.
    """
    text = text.replace("$", "").replace(" ", "").replace("\xa0", "")
    if not text:
        return None
    negative = False
    if text.startswith("(") and text.endswith(")"):
        text, negative = text[1:-1], True
    elif text.endswith("-"):
        text, negative = text[:-1], True
    if negative and text[:1] in ("+", "-"):
        raise ValueError("Two signs on one amount")
    sign = text[:1] if text[:1] in ("+", "-") else ""
    number = text[len(sign) :]
    if "," in number:
        if not _THOUSANDS.fullmatch(number):
            raise ValueError("Comma isn't a thousands separator")
        number = number.replace(",", "")
    cents = dollars_to_cents(sign + number)
    return -cents if negative else cents


def parse_date(text: str, date_format: str) -> dt.date:
    code = DATE_FORMATS[date_format]
    text = text.strip()
    if " " not in code:  # drop a time of day: "01/05/2026 10:30" or "2026-01-05T10:30"
        text = text.split(" ")[0].split("T")[0]
    return dt.datetime.strptime(text, code).date()


def _reads(value: str, date_format: str) -> bool:
    try:
        parse_date(value, date_format)
    except ValueError:
        return False
    return True


def _detect_date_format(values: list[str]) -> str | None:
    """The format that reads the most of these dates (US first on a tie), if it reads at least
    half of them. A stray bad row then shows up as a problem instead of hiding the column."""
    values = [v for v in values if v.strip()][:200]
    scores = {name: sum(_reads(v, name) for v in values) for name in DATE_FORMATS}
    best = max(scores, key=scores.get, default=None)
    return best if values and scores[best] * 2 >= len(values) else None


def clean_description(text: str) -> str:
    """One line, at most 500 characters. Text that a spreadsheet would run as a formula gets a
    leading apostrophe, so it's shown as text if it's ever exported and opened again."""
    text = _SPACES.sub(" ", _CONTROL.sub(" ", text)).strip()
    if text.startswith(FORMULA_STARTS):
        text = "'" + text
    return text[:MAX_DESCRIPTION]


def _cell(row: list[str], column: int) -> str:
    if column >= len(row):
        raise _RowProblem("This row has fewer columns than the others.")
    return row[column].strip()


def _amount(row: list[str], column: int | None, what: str) -> int | None:
    if column is None:
        return None
    try:
        return parse_amount(_cell(row, column))
    except ValueError:
        raise _RowProblem(f"The {what} isn't a dollar amount we can read.") from None


def _parse_row(row: list[str], m: CsvMapping) -> tuple[dt.date, str, int]:
    try:
        date = parse_date(_cell(row, m.date_column), m.date_format)
    except ValueError:
        raise _RowProblem(f"The date isn't in the {m.date_format} format.") from None
    description = clean_description(_cell(row, m.description_column))
    if not description:
        raise _RowProblem("The description is empty.")
    if m.amount_column is not None:
        cents = _amount(row, m.amount_column, "amount")
    else:
        debit = _amount(row, m.debit_column, "money-out amount")
        credit = _amount(row, m.credit_column, "money-in amount")
        if debit and credit:
            raise _RowProblem("Both the money-out and the money-in amounts are filled in.")
        cents = None if debit is None and credit is None else abs(credit or 0) - abs(debit or 0)
    if cents is None:
        raise _RowProblem("The amount is empty.")
    if cents == 0:
        raise _RowProblem("The amount is zero.")
    return date, description, -cents if m.flip_sign else cents


def fingerprint(account_id: int, date: dt.date, cents: int, description: str, nth: int) -> str:
    key = json.dumps(["v1", account_id, date.isoformat(), cents, description.casefold(), nth])
    return hashlib.sha256(key.encode()).hexdigest()


def _norm(name: str) -> str:
    return _SPACES.sub(" ", re.sub(r"[^a-z ]", " ", name.casefold())).strip()


def _pick_by_name(names: list[str]) -> dict:
    picked: dict = {}
    for role, words in _HEADER_WORDS.items():
        for word in words:
            col = next((i for i, n in enumerate(names) if word in n), None)
            if col is not None and col not in picked.values():
                picked[role] = col
                break
    if "amount_column" in picked:
        picked.pop("debit_column", None)
        picked.pop("credit_column", None)
    return picked


def _detect(rows: list[list[str]]) -> dict:
    """Guess the columns from the column names, or from the cells if there's no header row."""
    for index, row in enumerate(rows[:10]):
        names = [_norm(c) for c in row]
        if any("date" in n for n in names) and any(w in n for n in names for w in _MONEY_WORDS):
            return {"header_rows": index + 1, **_pick_by_name(names)}

    data = [r for r in rows[:50] if any(c.strip() for c in r)]
    width = max((len(r) for r in data), default=0)
    cols = [[r[i] for r in data if i < len(r) and r[i].strip()] for i in range(width)]
    date = next((i for i, v in enumerate(cols) if v and _detect_date_format(v)), None)
    amount = next((i for i, v in enumerate(cols) if i != date and v and _all_amounts(v)), None)
    texts = [i for i in range(width) if i not in (date, amount) and cols[i]]
    description = max(texts, key=lambda i: sum(len(x) for x in cols[i]), default=None)
    found = {"date_column": date, "amount_column": amount, "description_column": description}
    return {"header_rows": 0, **{k: v for k, v in found.items() if v is not None}}


def _all_amounts(values: list[str]) -> bool:
    try:
        return all(parse_amount(v) is not None for v in values)
    except ValueError:
        return False


def _columns_used(mapping: CsvMapping) -> list[int]:
    cols = [mapping.date_column, mapping.description_column]
    return cols + [c for c in (getattr(mapping, f) for f in AMOUNT_COLUMNS) if c is not None]


def _saved_mapping(session: Session, account_id: int) -> CsvMapping | None:
    saved = session.get(CsvImportMapping, account_id)
    if saved is None:
        return None
    try:
        return CsvMapping.model_validate_json(saved.mapping)
    except ValidationError:  # saved by an older version that no longer fits
        return None


def _mapping(base: dict, choices: MappingChoices, rows: list[list[str]]) -> CsvMapping | None:
    """The saved or detected mapping with the user's choices on top. None if incomplete."""
    picked = choices.model_dump(include=set(MappingChoices.model_fields), exclude_none=True)
    values = dict(base)
    if picked.keys() & set(AMOUNT_COLUMNS):  # choosing amount columns replaces the old ones
        for field in AMOUNT_COLUMNS:
            values.pop(field, None)
    values |= picked
    if "date_format" not in values and "date_column" in values:
        start, col = values.get("header_rows", 1), values["date_column"]
        dates = [r[col] for r in rows[start:] if col < len(r)]
        if found := _detect_date_format(dates):
            values["date_format"] = found
    try:
        return CsvMapping.model_validate(values)
    except ValidationError as exc:
        errors = exc.errors()
        if not picked or any(e["type"] == "missing" for e in errors):
            return None
        message = errors[0]["msg"].removeprefix("Value error, ")
        raise ApiError(422, "invalid_mapping", message) from None


def _prepare(session: Session, account_id: int, data: bytes, choices: MappingChoices) -> _Prepared:
    get_account(session, account_id)
    text = decode_csv(data)
    delimiter = choices.delimiter or _detect_delimiter(text)
    rows = _read_rows(text, delimiter)
    width = max(len(r) for r in rows)

    saved = _saved_mapping(session, account_id)
    used_saved = (
        saved is not None and saved.delimiter == delimiter and max(_columns_used(saved)) < width
    )
    base = saved.model_dump() if used_saved else {**_detect(rows), "delimiter": delimiter}
    mapping = _mapping(base, choices, rows)
    if mapping is not None and max(_columns_used(mapping)) >= width:
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
    return _Prepared(mapping, used_saved and mapping is not None, columns, sample, parsed)


def _parse_rows(
    session: Session, account_id: int, rows: list[list[str]], mapping: CsvMapping
) -> list[tuple[PreviewRow, str | None]]:
    seen: Counter = Counter()
    parsed: list[tuple[PreviewRow, str | None]] = []
    for number, row in enumerate(rows[mapping.header_rows :], start=mapping.header_rows + 1):
        if not any(c.strip() for c in row):
            continue
        try:
            date, description, cents = _parse_row(row, mapping)
        except _RowProblem as problem:
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
        message=None if p.mapping else NEED_COLUMNS,
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
    session.add_all(
        Transaction(
            account_id=account_id,
            date=r.date,
            amount_cents=r.amount_cents,
            description=r.description,
            source=TransactionSource.CSV,
            kind=TransactionKind.NORMAL,
            import_fingerprint=fp,
        )
        for r, fp in new
    )
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
    return ImportResult(
        imported=len(new),
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
