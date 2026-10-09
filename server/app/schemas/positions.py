"""Positions from a broker's file (``services/positions``): what an account held on a day."""

import datetime as dt
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import Id, Schema

NOTE = (
    "From your broker's positions file, as of the date shown. It doesn't change your purchases "
    "or gains: those come from the purchases and sales you record. A difference means a purchase "
    "or sale may be missing there."
)


class PositionsChoices(Schema):
    """Query parameters for the preview and the import."""

    account_id: Id
    as_of: dt.date  # the day the file is from (positions files rarely say)
    file_name: str | None = Field(None, max_length=200)  # for the import history

    @field_validator("as_of")
    @classmethod
    def _not_future(cls, value: dt.date) -> dt.date:
        if value > dt.date.today():
            raise ValueError("The file's date can't be in the future.")
        return value


class PositionPreviewRow(Schema):
    row_number: int
    symbol: str | None = None
    shares: str | None = None
    cost_basis_cents: int | None = None
    value_cents: int | None = None
    price_cents: int | None = None
    status: Literal["ok", "skipped"] = "ok"
    problem: str | None = None  # why a row was skipped (a cash line, a note at the bottom...)


class PositionsPreview(Schema):
    columns: dict[str, int]  # which column holds what, counting from 0
    positions: int
    skipped: int
    rows: list[PositionPreviewRow]  # every position (combined by symbol), then skipped rows


class PositionsResult(Schema):
    positions: int
    prices_updated: int
    skipped: int


class PositionOut(Schema):
    symbol: str
    shares_micro: int
    shares: str
    cost_basis_cents: int | None
    value_cents: (
        int | None
    )  # from the file, or shares x your latest price (today's, not the file's)
    recorded_shares_micro: (
        int  # what your recorded purchases and sales add up to on the file's date
    )
    matches: bool


class AccountPositionsOut(Schema):
    account_id: int
    account_name: str
    as_of: dt.date
    positions: list[PositionOut]
    value_cents: int | None  # None if any position has no value


class PositionsOut(Schema):
    accounts: list[AccountPositionsOut]
    note: str = NOTE
