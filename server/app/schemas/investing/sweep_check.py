"""Checking deposit sweeps by hand (``services/investing/sweep_check``). Amounts are cents."""

import datetime as dt
from typing import Annotated, Literal

from pydantic import Field

from app.schemas.common import MAX_ID, Schema


class PossibleMatch(Schema):
    kind: Literal["dividend", "trade"]
    record_id: int  # the dividend's or trade's id, for Link
    transaction_id: int
    date: dt.date
    description: str
    amount_cents: int  # signed, as in the transaction
    exact: bool  # exactly the opposite of the sweep's amount
    gap_cents: int  # how far the amounts are apart; linked anyway, this isn't counted anywhere
    days_apart: int  # the sweep's date minus this one's


class UnlinkedSweep(Schema):
    transaction_id: int
    date: dt.date
    description: str
    amount_cents: int
    account_id: int
    account_name: str
    matches: list[PossibleMatch]  # exact amounts first, then the closest dates


class AccountCount(Schema):
    account_id: int
    account_name: str
    payments: int  # dividends and trades, not counting ones marked "not one"
    with_sweep: int
    free_sweeps: int  # sweep lines in it not linked to anything


class SweepCheck(Schema):
    accounts: list[AccountCount]
    unlinked: list[UnlinkedSweep]
    suggest_days: int


class SweepLink(Schema):
    kind: Literal["dividend", "trade"]
    record_id: Annotated[int, Field(ge=1, le=MAX_ID)]
    confirm: bool = False  # you accept that a gap between the amounts isn't counted anywhere
