"""Stock CSV import: purchases and sales from a spreadsheet or a broker's export.

The columns are found from the header row's names (see ``services/imports/stock_csv``); there's no
column picker. Each row becomes a purchase (lot) or a sale, in one account or none.
"""

import datetime as dt
from typing import Literal

from pydantic import Field

from app.schemas.common import Id, Schema

Kind = Literal["buy", "sell"]


class StockImportChoices(Schema):
    """Query parameters for both the preview and the import."""

    account_id: Id | None = None  # the account the shares are in; none if left out


class StockCommitChoices(StockImportChoices):
    skip_invalid_rows: bool = False
    file_name: str | None = Field(None, max_length=200)  # for the import history


class StockColumns(Schema):
    """Which column (counting from 0) holds what. ``kind`` is optional: without it every row is a
    purchase. ``money`` is the total paid including fees, or received after fees."""

    symbol: int
    date: int
    shares: int
    money: int
    kind: int | None = None
    date_format: str | None = None  # None if no format reads the dates


class StockPreviewRow(Schema):
    row_number: int  # as a spreadsheet would number it, counting the header row
    kind: Kind | None = None
    symbol: str | None = None
    date: dt.date | None = None
    shares: str | None = None
    money_cents: int | None = None  # cost for a purchase, money received for a sale
    status: Literal["new", "duplicate", "invalid"] = "new"
    problem: str | None = None


class StockImportPreview(Schema):
    columns: StockColumns
    total_rows: int
    new_buys: int
    new_sells: int
    duplicate_rows: int
    invalid_rows: int
    rows: list[StockPreviewRow]  # the first rows, plus every row with a problem (both capped)


class StockImportResult(Schema):
    purchases_added: int
    sales_added: int
    skipped_duplicates: int
    skipped_invalid: int
