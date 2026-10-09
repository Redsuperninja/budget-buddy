"""Stock trades found in a bank-style file (``services/bank_trades``). Amounts are cents; shares are
millionths of a share."""

import datetime as dt
from typing import Literal

from app.schemas.common import Schema


class BankTradeOut(Schema):
    id: int
    transaction_id: int
    sweep_transaction_id: int | None
    date: dt.date
    account_id: int
    account_name: str
    security: str  # the company, from the description: "ABBOTT LABORATORIES"
    side: Literal["buy", "sell"]  # money out is a buy, money in a sale
    amount_cents: int  # what it cost, or what the sale brought in (positive)
    # Once recorded as a stock purchase or sale: its ticker, shares and price per share.
    recorded: bool
    symbol: str | None
    shares_micro: int | None
    price_cents: int | None
    # The ticker to offer: the one you gave this company before, or one in the description.
    suggested_symbol: str | None


class BankTradesOut(Schema):
    items: list[BankTradeOut]


class BankTradesFound(Schema):
    found: int
    sweeps_linked: int
