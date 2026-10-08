"""Reading a bank CSV: decode the bytes, split rows, parse each cell, fingerprint rows.

Imported rows are ordinary ("normal") transactions with ``source = "csv"``. Nothing in this
module logs file contents, descriptions or amounts, and error messages only ever name row numbers.

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

from app.errors import ApiError
from app.money import dollars_to_cents
from app.schemas.csv_import import DATE_FORMATS, CsvMapping

MAX_ROWS = 10_000
MAX_DESCRIPTION = 500
# A spreadsheet treats a cell starting with one of these as a formula ("CSV injection").
FORMULA_STARTS = ("=", "+", "-", "@")
DELIMITERS = (",", ";", "\t", "|")

_THOUSANDS = re.compile(r"[0-9]{1,3}(,[0-9]{3})+(\.[0-9]+)?")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
SPACES = re.compile(r"\s+")


class RowProblem(Exception):
    pass


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


def detect_delimiter(text: str) -> str:
    """The separator that splits the first lines into the most columns (comma on a tie)."""
    lines = [line for line in text.splitlines()[:30] if line.strip()]
    best, best_count = ",", 1
    for delimiter in DELIMITERS:
        counts = Counter(len(row) for row in csv.reader(lines, delimiter=delimiter))
        count = counts.most_common(1)[0][0]
        if count > best_count:
            best, best_count = delimiter, count
    return best


def read_rows(text: str, delimiter: str) -> list[list[str]]:
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


def clean_description(text: str) -> str:
    """One line, at most 500 characters. Text that a spreadsheet would run as a formula gets a
    leading apostrophe, so it's shown as text if it's ever exported and opened again."""
    text = SPACES.sub(" ", _CONTROL.sub(" ", text)).strip()
    if text.startswith(FORMULA_STARTS):
        text = "'" + text
    return text[:MAX_DESCRIPTION]


def _cell(row: list[str], column: int) -> str:
    if column >= len(row):
        raise RowProblem("This row has fewer columns than the others.")
    return row[column].strip()


def _amount(row: list[str], column: int | None, what: str) -> int | None:
    if column is None:
        return None
    try:
        return parse_amount(_cell(row, column))
    except ValueError:
        raise RowProblem(f"The {what} isn't a dollar amount we can read.") from None


def parse_row(row: list[str], m: CsvMapping) -> tuple[dt.date, str, int]:
    try:
        date = parse_date(_cell(row, m.date_column), m.date_format)
    except ValueError:
        raise RowProblem(f"The date isn't in the {m.date_format} format.") from None
    description = clean_description(_cell(row, m.description_column))
    if not description:
        raise RowProblem("The description is empty.")
    if m.amount_column is not None:
        cents = _amount(row, m.amount_column, "amount")
    else:
        debit = _amount(row, m.debit_column, "money-out amount")
        credit = _amount(row, m.credit_column, "money-in amount")
        if debit and credit:
            raise RowProblem("Both the money-out and the money-in amounts are filled in.")
        cents = None if debit is None and credit is None else abs(credit or 0) - abs(debit or 0)
    if cents is None:
        raise RowProblem("The amount is empty.")
    if cents == 0:
        raise RowProblem("The amount is zero.")
    return date, description, -cents if m.flip_sign else cents


def fingerprint(account_id: int, date: dt.date, cents: int, description: str, nth: int) -> str:
    key = json.dumps(["v1", account_id, date.isoformat(), cents, description.casefold(), nth])
    return hashlib.sha256(key.encode()).hexdigest()
