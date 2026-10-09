"""Brokerage activity import: a broker's history file into one account
(services/activity_import.py)."""

import datetime as dt
from typing import Literal

from pydantic import Field

from app.schemas.common import Schema


class ActivityChoices(Schema):
    """Query parameters for the import (the preview takes none)."""

    skip_invalid_rows: bool = False
    file_name: str | None = Field(None, max_length=200)  # for the import history


class ActivityColumns(Schema):
    """Which column (counting from 0) holds what. ``action`` is the activity's wording ("YOU
    BOUGHT", "DIVIDEND RECEIVED"); ``symbol`` and ``shares`` are needed for stock trades only."""

    date: int
    action: int
    amount: int
    symbol: int | None = None
    shares: int | None = None
    description: int | None = None  # the security's name, added to the transaction's wording
    date_format: str | None = None


class ActivityPreviewRow(Schema):
    row_number: int
    date: dt.date | None = None
    description: str | None = None
    amount_cents: int | None = None
    trade: str | None = None  # "Buy 2 VTI" when it becomes a stock trade
    status: Literal["new", "duplicate", "invalid"] = "new"
    problem: str | None = None


class ActivityPreview(Schema):
    columns: ActivityColumns
    total_rows: int
    new_rows: int
    new_trades: int
    duplicate_rows: int
    invalid_rows: int
    rows: list[ActivityPreviewRow]  # the first rows, plus every row with a problem (both capped)


class ActivityResult(Schema):
    imported: int
    trades: int  # purchases and sales recorded from the buys and sells
    dividends_found: int
    categorized: int
    transfers_matched: int
    skipped_duplicates: int
    skipped_invalid: int
