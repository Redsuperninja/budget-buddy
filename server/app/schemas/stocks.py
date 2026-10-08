"""Stock lots (purchases), sales, and realized gains.

Shares: send ``shares`` as text ("2.5") or ``shares_micro`` as whole millionths of a share
(2_500_000). Never a float. Money: send ``..._cents`` or the dollar text field, not both.
"""

import datetime as dt
from typing import Annotated

from pydantic import AfterValidator, Field, model_validator

from app.money import MAX_ABS_CENTS
from app.schemas.common import DollarText, Id, Schema, pick_cents
from app.services.stock_gains import Term
from app.shares import MAX_SHARES_MICRO, shares_to_micro

# Shown with the wash-sale flag and when a retirement account or HSA is refused.
WASH_SALE_LIMITS = (
    "We compare purchases of the same symbol entered here, in any account, including an IRA or "
    "HSA. A spouse buying it within 30 days of a sale at a loss can also cause a wash sale; we "
    "don't know about those purchases."
)
ESTIMATE_NOTE = (
    "This is an estimate, not tax advice. Check it against the Form 1099-B from your broker. "
    "A possible wash sale is only flagged here: the loss isn't adjusted, and part or all of it "
    "may not be deductible this year. " + WASH_SALE_LIMITS
)


def _symbol(text: str) -> str:
    text = text.strip().upper()
    if (
        not text
        or len(text) > 16
        or not all(c.isascii() and (c.isalnum() or c in ".-") for c in text)
    ):
        raise ValueError("Enter a stock symbol like VTI or BRK.B (letters, numbers, . or -).")
    return text


def _shares_text(text: str) -> str:
    try:
        shares_to_micro(text)
    except ValueError as exc:
        raise ValueError(f"{exc}.") from None
    return text


Symbol = Annotated[str, Field(strict=True, max_length=40), AfterValidator(_symbol)]
SharesMicro = Annotated[int, Field(strict=True, gt=0, lt=MAX_SHARES_MICRO)]
SharesText = Annotated[str, Field(strict=True, max_length=40), AfterValidator(_shares_text)]
NonNegativeCents = Annotated[int, Field(strict=True, ge=0, lt=MAX_ABS_CENTS)]


def _resolve_shares(shares_micro: int | None, shares: str | None) -> int:
    if shares_micro is not None and shares is not None:
        raise ValueError("Send either shares or shares_micro, not both.")
    if shares is not None:
        shares_micro = shares_to_micro(shares)
    if shares_micro is None:
        raise ValueError("The number of shares is required: send shares or shares_micro.")
    if shares_micro <= 0:
        raise ValueError("The number of shares must be more than zero.")
    return shares_micro


def _resolve_money(cents: int | None, dollars: str | None, what: str) -> int:
    cents = pick_cents(cents, dollars, what)
    if cents is None:
        raise ValueError(f"The {what.replace('_', ' ')} is required: send {what}_cents or {what}.")
    if cents < 0:
        raise ValueError(f"The {what.replace('_', ' ')} can't be negative.")
    return cents


class LotCreate(Schema):
    """Shares you bought in one purchase. ``cost_basis`` is the total you paid, including fees."""

    account_id: Id | None = None
    symbol: Symbol
    acquired_on: dt.date
    shares_micro: SharesMicro | None = None
    shares: SharesText | None = None
    cost_basis_cents: NonNegativeCents | None = None
    cost_basis: DollarText | None = None

    @model_validator(mode="after")
    def _resolve(self):
        self.shares_micro = _resolve_shares(self.shares_micro, self.shares)
        self.cost_basis_cents = _resolve_money(self.cost_basis_cents, self.cost_basis, "cost_basis")
        self.shares = self.cost_basis = None
        return self


class SaleCreate(Schema):
    """Shares you sold. ``proceeds`` is the total you received, after fees."""

    account_id: Id | None = None
    symbol: Symbol
    sold_on: dt.date
    shares_micro: SharesMicro | None = None
    shares: SharesText | None = None
    proceeds_cents: NonNegativeCents | None = None
    proceeds: DollarText | None = None

    @model_validator(mode="after")
    def _resolve(self):
        self.shares_micro = _resolve_shares(self.shares_micro, self.shares)
        self.proceeds_cents = _resolve_money(self.proceeds_cents, self.proceeds, "proceeds")
        self.shares = self.proceeds = None
        return self


class LotOut(Schema):
    id: int
    account_id: int | None
    symbol: str
    acquired_on: dt.date
    shares_micro: int
    shares: str  # the same number as text, e.g. "2.5"
    cost_basis_cents: int
    remaining_shares_micro: int  # not sold yet
    remaining_shares: str
    long_term_from: dt.date  # shares sold on or after this date are long term
    created_at: dt.datetime
    updated_at: dt.datetime


class RealizedOut(Schema):
    """The part of a sale that came out of one purchase lot. Gain is negative for a loss."""

    lot_id: int
    acquired_on: dt.date
    shares_micro: int
    shares: str
    proceeds_cents: int
    cost_basis_cents: int
    gain_cents: int
    term: Term  # "short" (held one year or less) or "long" (more than one year)
    possible_wash_sale: bool


class SaleOut(Schema):
    id: int
    account_id: int | None
    symbol: str
    sold_on: dt.date
    shares_micro: int
    shares: str
    proceeds_cents: int
    cost_basis_cents: int
    gain_cents: int
    possible_wash_sale: bool
    # False inside a retirement account or HSA: not taxed, left out of the gains summary.
    taxed: bool = True
    lots: list[RealizedOut]  # which purchases the shares came from (oldest first: FIFO)
    note: str = ESTIMATE_NOTE
    created_at: dt.datetime
    updated_at: dt.datetime


class TermTotalsOut(Schema):
    proceeds_cents: int
    cost_basis_cents: int
    gain_cents: int


class GainsSummaryOut(Schema):
    """Realized gains for sales dated in one tax year. Losses are negative."""

    tax_year: int
    short_term: TermTotalsOut
    long_term: TermTotalsOut
    total_gain_cents: int
    possible_wash_sale_count: int
    sales: list[SaleOut]
    note: str = ESTIMATE_NOTE
