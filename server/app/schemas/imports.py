"""Import history (services/imports.py)."""

import datetime as dt
from typing import Literal

from app.schemas.common import Schema

ImportKind = Literal["bank", "stocks", "activity", "positions"]


class ImportOut(Schema):
    id: int
    kind: ImportKind
    account_id: int | None
    account_name: str | None  # None when it had no account, or the account was deleted
    file_name: str
    rows_added: int
    created_at: dt.datetime
