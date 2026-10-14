"""Working out a CSV's columns: guess them from the header words or the cells, then apply the
user's choices on top of the saved or guessed mapping."""

import re

from pydantic import ValidationError

from app.errors import ApiError
from app.schemas.imports.csv_import import DATE_FORMATS, CsvMapping, MappingChoices
from app.services.imports.csv_parsing import SPACES, parse_amount, parse_date

AMOUNT_COLUMNS = ("amount_column", "debit_column", "credit_column")

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


def _reads(value: str, date_format: str) -> bool:
    try:
        parse_date(value, date_format)
    except ValueError:
        return False
    return True


def detect_date_format(values: list[str]) -> str | None:
    """The format that reads the most of these dates (US first on a tie), if it reads at least
    half of them. A stray bad row then shows up as a problem instead of hiding the column."""
    values = [v for v in values if v.strip()][:200]
    scores = {name: sum(_reads(v, name) for v in values) for name in DATE_FORMATS}
    best = max(scores, key=scores.get, default=None)
    return best if values and scores[best] * 2 >= len(values) else None


def _norm(name: str) -> str:
    return SPACES.sub(" ", re.sub(r"[^a-z ]", " ", name.casefold())).strip()


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


def detect_columns(rows: list[list[str]]) -> dict:
    """Guess the columns from the column names, or from the cells if there's no header row."""
    for index, row in enumerate(rows[:10]):
        names = [_norm(c) for c in row]
        if any("date" in n for n in names) and any(w in n for n in names for w in _MONEY_WORDS):
            return {"header_rows": index + 1, **_pick_by_name(names)}

    data = [r for r in rows[:50] if any(c.strip() for c in r)]
    width = max((len(r) for r in data), default=0)
    cols = [[r[i] for r in data if i < len(r) and r[i].strip()] for i in range(width)]
    date = next((i for i, v in enumerate(cols) if v and detect_date_format(v)), None)
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


def columns_used(mapping: CsvMapping) -> list[int]:
    cols = [mapping.date_column, mapping.description_column]
    return cols + [c for c in (getattr(mapping, f) for f in AMOUNT_COLUMNS) if c is not None]


def build_mapping(base: dict, choices: MappingChoices, rows: list[list[str]]) -> CsvMapping | None:
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
        if found := detect_date_format(dates):
            values["date_format"] = found
    try:
        return CsvMapping.model_validate(values)
    except ValidationError as exc:
        errors = exc.errors()
        if not picked or any(e["type"] == "missing" for e in errors):
            return None
        message = errors[0]["msg"].removeprefix("Value error, ")
        raise ApiError(422, "invalid_mapping", message) from None
