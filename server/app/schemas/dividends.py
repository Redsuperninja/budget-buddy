"""Dividends found in your transactions (``services/dividend_matching``). Amounts are cents."""

import datetime as dt

from app.schemas.common import Schema

NOTE = (
    "This is an estimate, not tax advice. Check it against the Form 1099-DIV from your broker, "
    "which also says how much is qualified (usually taxed at a lower rate). A dividend counts in "
    "the year it was paid, except one declared in October to December and paid in January, "
    "which your 1099-DIV counts in the year before. Dividends inside a retirement account or HSA "
    "aren't taxed now, while they stay in the account."
)


class DividendOut(Schema):
    id: int
    transaction_id: int
    sweep_transaction_id: int | None  # the deposit sweep that moved the same cash on, if found
    account_id: int
    payer: str
    paid_on: dt.date
    amount_cents: int
    taxed: bool  # False inside a retirement account or HSA


class DividendsOut(Schema):
    """Dividends paid in one tax year, oldest first."""

    tax_year: int
    dividends: list[DividendOut]
    total_cents: int
    taxed_cents: int  # the part outside retirement accounts and HSAs
    note: str = NOTE


class DividendsFound(Schema):
    found: int
    sweeps_linked: int
