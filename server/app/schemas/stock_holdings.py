"""What you hold now, by account, and the prices you type in (services/stock_holdings.py)."""

import datetime as dt

from pydantic import model_validator

from app.models import AccountKind
from app.schemas.common import DollarText, Schema, pick_cents
from app.schemas.stocks import NonNegativeCents, Symbol


class PriceIn(Schema):
    """Send ``price_cents`` (per share) or ``price`` as dollar text, not both."""

    symbol: Symbol
    price_cents: NonNegativeCents | None = None
    price: DollarText | None = None
    as_of: dt.date

    @model_validator(mode="after")
    def _price(self):
        cents = pick_cents(self.price_cents, self.price, "price")
        if cents is None or cents < 0:
            raise ValueError("Enter the price of one share, like 245.10.")
        self.price_cents, self.price = cents, None
        return self


class HoldingOut(Schema):
    symbol: str
    shares_micro: int
    shares: str
    cost_basis_cents: int  # what the shares still held cost, including fees
    price_cents: int | None  # your latest price, or None if you haven't entered one
    price_as_of: dt.date | None
    price_source: str | None  # "you" (typed in), "feed" (Finnhub, ADR-0010) or "file" (positions)
    price_fetched_at: dt.datetime | None  # UTC, feed prices only
    value_cents: int | None
    unrealized_gain_cents: int | None  # value minus cost; not taxed until sold


class AccountHoldingsOut(Schema):
    account_id: int | None
    account_name: str
    account_kind: AccountKind | None
    retirement_type: str | None = None  # Roth IRA, 401(k)... for retirement accounts
    taxed: bool  # False for retirement accounts and HSAs
    holdings: list[HoldingOut]
    cost_basis_cents: int
    value_cents: int | None  # None if any holding has no price yet


class HoldingsOut(Schema):
    accounts: list[AccountHoldingsOut]
    cost_basis_cents: int
    value_cents: int | None
    note: str
