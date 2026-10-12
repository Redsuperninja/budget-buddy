"""Reading a brokerage activity (history) file: columns by name, then one row at a time.

Each row is a transaction (date, wording, signed amount: money out negative). A row whose wording
says it's a buy or a sell, with a symbol and a number of shares, is also a stock trade. Wording
like "Sell Short" or an option, and the money market fund that holds the account's cash, are
transactions only. A row with no money is skipped (``SharesOnly``). Error messages never repeat a
cell.
"""

import re
from dataclasses import dataclass

from pydantic import ValidationError

from app.errors import ApiError
from app.schemas.imports.activity_import import ActivityColumns
from app.schemas.imports.stock_import import Kind
from app.schemas.investing.stocks import LotCreate, SaleCreate
from app.services.imports.csv_columns import detect_date_format
from app.services.imports.csv_headers import HEADER_SEARCH_ROWS, header_name, pick_columns
from app.services.imports.csv_parsing import (
    RowProblem,
    cell,
    clean_description,
    parse_amount,
    parse_date,
)
from app.services.imports.stock_csv import shares_and_sign, trade_kind

NO_COLUMNS = (
    "We couldn't find the columns. A brokerage activity file needs column names for the date, the "
    'action (like "YOU BOUGHT" or "DIVIDEND RECEIVED") and the amount in its first rows.'
)
_WORDS = {
    "date": ("run date", "trade date", "transaction date", "activity date", "date"),
    "action": ("action", "activity", "transaction type", "type", "transaction"),
    "amount": ("amount", "net amount", "total"),
    "symbol": ("symbol", "ticker"),
    "shares": ("quantity", "shares", "qty"),
    "description": ("security description", "description", "security name", "name"),
}
_AVOID = {
    "date": ("settle",),
    "amount": ("price", "commission", "fee", "per share", "accrued"),
    "shares": ("price",),
}


# A money market (cash) fund: buying it is the account's cash sweep, and its "sales" are
# redemptions with no sell wording, so it's never recorded as a stock trade.
_MONEY_MARKET_SYMBOL = re.compile(r"[A-Z]{3}XX")
_MONEY_MARKET_WORDS = re.compile(r"money market|core account|core position|sweep", re.I)


class SharesOnly(RowProblem):
    """A row where no money moved (shares moved in or out, a split): skipped, not a problem."""


@dataclass
class ActivityRow:
    row_number: int
    date: object
    description: str
    amount_cents: int
    kind: Kind | None  # set when the row is also a stock trade
    trade: LotCreate | SaleCreate | None


def find_columns(rows: list[list[str]]) -> tuple[int, ActivityColumns]:
    for index, row in enumerate(rows[:HEADER_SEARCH_ROWS]):
        picked = pick_columns(
            [header_name(c) for c in row], _WORDS, _AVOID, required={"date", "action", "amount"}
        )
        if picked:
            dates = [r[picked["date"]] for r in rows[index + 1 :] if picked["date"] < len(r)]
            return index, ActivityColumns(**picked, date_format=detect_date_format(dates))
    raise ApiError(422, "columns_not_found", NO_COLUMNS)


def _optional(row: list[str], column: int | None) -> str:
    return row[column].strip() if column is not None and column < len(row) else ""


def _wording(action: str, symbol: str, name: str) -> str:
    parts = [action]
    if name and name.casefold() not in action.casefold():
        parts.append(name)
    if symbol and symbol.casefold() not in action.casefold():
        parts.append(f"({symbol})")
    return clean_description(" ".join(parts))


def _trade(row: list[str], cols: ActivityColumns, action: str, date, cents: int, account_id: int):
    """The stock trade a buy or sell row also is, or (None, None) when it isn't a plain one."""
    symbol = _optional(row, cols.symbol).rstrip("*")
    shares_text = _optional(row, cols.shares)
    if not symbol or not shares_text:
        return None, None
    if _MONEY_MARKET_SYMBOL.fullmatch(symbol.upper()) or _MONEY_MARKET_WORDS.search(
        " ".join([action, _optional(row, cols.description)])
    ):
        return None, None  # the cash sweep: a transaction only
    try:
        kind = trade_kind(action)
    except RowProblem:
        return None, None
    if (cents < 0) != (kind == "buy"):
        return None, None  # a buy must be money out, a sale money in
    shares, _ = shares_and_sign(shares_text)
    common = {"account_id": account_id, "symbol": symbol, "shares": shares}
    try:
        if kind == "buy":
            return kind, LotCreate(**common, acquired_on=date, cost_basis_cents=-cents)
        return kind, SaleCreate(**common, sold_on=date, proceeds_cents=cents)
    except ValidationError:
        return None, None  # an odd symbol or share count: keep it as a transaction only


def parse_row(row: list[str], number: int, cols: ActivityColumns, account_id: int) -> ActivityRow:
    if cols.date_format is None:
        raise RowProblem("The dates aren't in a format we know, like 2026-01-31 or 01/31/2026.")
    try:
        date = parse_date(cell(row, cols.date), cols.date_format)
    except ValueError:
        raise RowProblem(f"The date isn't in the {cols.date_format} format.") from None
    action = cell(row, cols.action)
    try:
        cents = parse_amount(cell(row, cols.amount))
    except ValueError:
        raise RowProblem("The amount isn't a dollar amount we can read.") from None
    if not cents:
        raise SharesOnly("No money moved (shares moved in or out, or a split): nothing to add.")
    symbol = _optional(row, cols.symbol).rstrip("*")
    description = _wording(action, symbol, _optional(row, cols.description))
    if not description:
        raise RowProblem("The action is empty.")
    kind, trade = _trade(row, cols, action, date, cents, account_id)
    return ActivityRow(number, date, description, cents, kind, trade)
