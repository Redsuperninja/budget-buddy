"""Reading a stock CSV: find the columns from the header row, then turn each row into a purchase
or a sale. Decoding and cell parsing are shared with the bank import (``csv_parsing``).

Each row is checked with the same schemas as a purchase or sale typed in by hand, so the rules
(symbol, whole millionths of a share, cents) are the same. Error messages only name the problem,
never the cell's contents.
"""

import re
from dataclasses import dataclass

from pydantic import ValidationError

from app.errors import ApiError
from app.schemas.stock_import import Kind, StockColumns
from app.schemas.stocks import LotCreate, SaleCreate
from app.services.csv_columns import detect_date_format
from app.services.csv_parsing import RowProblem, parse_amount, parse_date

HEADER_SEARCH_ROWS = 10
NO_COLUMNS = (
    "We couldn't find the columns. The first row of the file needs column names: Symbol, Date, "
    "Shares (or Quantity), and Cost (or Amount). To import sales too, add a Type column that says "
    "Buy or Sell on each row."
)

# Words in column names, matched in this order; a column is used once. The type column must be
# named exactly, so "Security Type" isn't taken for buy or sell.
_TYPE_NAMES = ("type", "action", "buy sell", "buy or sell", "side", "transaction type", "activity")
_WORDS = {
    "symbol": ("symbol", "ticker"),
    "date": ("trade date", "date acquired", "acquired", "purchase date", "date sold", "date"),
    "shares": ("quantity", "shares", "qty", "units"),
    "money": ("cost basis", "total cost", "proceeds", "net amount", "amount", "cost", "total"),
}
_BUY_WORDS = ("buy", "bought", "purchase", "reinvest")
_SELL_WORDS = ("sell", "sold", "sale")
_THOUSANDS = re.compile(r"[0-9]{1,3}(,[0-9]{3})+(\.[0-9]+)?")
_FIELD_NAMES = {
    "symbol": "symbol",
    "shares": "number of shares",
    "cost_basis_cents": "cost",
    "proceeds_cents": "amount received",
}


@dataclass
class ParsedRow:
    row_number: int
    kind: Kind
    trade: LotCreate | SaleCreate


def _norm(name: str) -> str:
    return " ".join(re.sub(r"[^a-z]", " ", name.casefold()).split())


def _pick(names: list[str]) -> dict | None:
    picked: dict = {}
    kind = next((i for i, n in enumerate(names) if n in _TYPE_NAMES), None)
    if kind is not None:
        picked["kind"] = kind
    for role, words in _WORDS.items():
        for word in words:
            col = next(
                (i for i, n in enumerate(names) if word in n and i not in picked.values()), None
            )
            if col is not None:
                picked[role] = col
                break
        else:
            return None
    return picked


def find_columns(rows: list[list[str]]) -> tuple[int, StockColumns]:
    """The header row's position (0-based) and the columns it names."""
    for index, row in enumerate(rows[:HEADER_SEARCH_ROWS]):
        picked = _pick([_norm(c) for c in row])
        if picked:
            dates = [r[picked["date"]] for r in rows[index + 1 :] if picked["date"] < len(r)]
            return index, StockColumns(**picked, date_format=detect_date_format(dates))
    raise ApiError(422, "columns_not_found", NO_COLUMNS)


def _cell(row: list[str], column: int) -> str:
    if column >= len(row):
        raise RowProblem("This row has fewer columns than the others.")
    return row[column].strip()


def _kind(text: str) -> Kind:
    text = text.casefold()
    is_buy = any(w in text for w in _BUY_WORDS)
    is_sell = any(w in text for w in _SELL_WORDS)
    if is_buy == is_sell:
        raise RowProblem("The type should say Buy or Sell.")
    return "buy" if is_buy else "sell"


def _shares(text: str) -> str:
    """Brokers often show shares sold as negative, and big numbers with commas."""
    text = text.lstrip("+-").strip()
    return text.replace(",", "") if _THOUSANDS.fullmatch(text) else text


def _money(text: str) -> int:
    """Total cost or money received, as positive cents. Brokers often show purchases as negative."""
    try:
        cents = parse_amount(text)
    except ValueError:
        raise RowProblem("The cost or amount isn't a dollar amount we can read.") from None
    if cents is None:
        raise RowProblem("The cost or amount is empty.")
    return abs(cents)


def _problem(exc: ValidationError) -> RowProblem:
    error = exc.errors()[0]
    if error["type"] == "value_error":
        return RowProblem(error["msg"].removeprefix("Value error, "))
    field = _FIELD_NAMES.get(str(error["loc"][0]) if error["loc"] else "", "row")
    return RowProblem(f"The {field} isn't something we can import.")


def parse_row(row: list[str], number: int, cols: StockColumns, account_id: int | None) -> ParsedRow:
    kind = _kind(_cell(row, cols.kind)) if cols.kind is not None else "buy"
    if cols.date_format is None:
        raise RowProblem("The dates aren't in a format we know, like 2026-01-31 or 01/31/2026.")
    try:
        date = parse_date(_cell(row, cols.date), cols.date_format)
    except ValueError:
        raise RowProblem(f"The date isn't in the {cols.date_format} format.") from None
    common = {
        "account_id": account_id,
        "symbol": _cell(row, cols.symbol),
        "shares": _shares(_cell(row, cols.shares)),
    }
    cents = _money(_cell(row, cols.money))
    try:
        if kind == "buy":
            trade = LotCreate(**common, acquired_on=date, cost_basis_cents=cents)
        else:
            trade = SaleCreate(**common, sold_on=date, proceeds_cents=cents)
    except ValidationError as exc:
        raise _problem(exc) from None
    return ParsedRow(number, kind, trade)
