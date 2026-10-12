"""Reading a broker's positions file: find the columns by name, then one position per row.

Rows that aren't a stock or fund (cash lines, totals, notes at the bottom) are skipped with a
reason, not refused: positions files have them. Fidelity marks its cash fund like "SPAXX**"; the
stars are dropped. Error messages never repeat a cell's contents.
"""

from dataclasses import dataclass

from app.errors import ApiError
from app.schemas.stocks import clean_symbol
from app.services.imports.csv_headers import HEADER_SEARCH_ROWS, header_name, pick_columns
from app.services.imports.csv_parsing import THOUSANDS, parse_amount
from app.shares import shares_to_micro

NO_COLUMNS = (
    "We couldn't find the columns. A positions file needs a Symbol column and a Quantity (or "
    "Shares) column in its first rows."
)
_WORDS = {
    "symbol": ("symbol", "ticker"),
    "shares": ("quantity", "shares", "qty", "units"),
    "cost": ("cost basis total", "total cost basis", "cost basis", "total cost"),
    "value": ("current value", "market value", "total value", "value"),
    "price": ("last price", "current price", "market price", "price"),
}
_AVOID = {
    "shares": ("percent",),
    "cost": ("per share", "average", "avg", "unit"),
    "value": ("change", "gain", "percent", "per share"),
    "price": ("change", "percent"),
}


@dataclass
class ParsedPosition:
    row_number: int
    symbol: str
    shares_micro: int
    cost_basis_cents: int | None
    value_cents: int | None
    price_cents: int | None


class Skip(Exception):
    pass


def find_columns(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    for index, row in enumerate(rows[:HEADER_SEARCH_ROWS]):
        picked = pick_columns(
            [header_name(c) for c in row], _WORDS, _AVOID, required={"symbol", "shares"}
        )
        if picked:
            return index, picked
    raise ApiError(422, "columns_not_found", NO_COLUMNS)


def _cell(row: list[str], column: int | None) -> str:
    return row[column].strip() if column is not None and column < len(row) else ""


def _money(text: str) -> int | None:
    """A dollar cell, or None when empty or not a number ("--", "n/a")."""
    try:
        cents = parse_amount(text)
    except ValueError:
        return None
    return None if cents is None else abs(cents)


def parse_position(row: list[str], number: int, cols: dict[str, int]) -> ParsedPosition:
    try:
        symbol = clean_symbol(_cell(row, cols["symbol"]).rstrip("*"))
    except ValueError:
        raise Skip("Not a stock or fund row.") from None
    shares = _cell(row, cols["shares"]).replace("$", "")
    shares = shares.replace(",", "") if THOUSANDS.fullmatch(shares) else shares
    try:
        shares_micro = shares_to_micro(shares)
    except ValueError:
        raise Skip("No number of shares (a cash line, or shares held short).") from None
    if shares_micro == 0:
        raise Skip("No shares held.")
    return ParsedPosition(
        number,
        symbol,
        shares_micro,
        _money(_cell(row, cols.get("cost"))),
        _money(_cell(row, cols.get("value"))),
        _money(_cell(row, cols.get("price"))),
    )
