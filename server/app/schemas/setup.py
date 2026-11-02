"""First-start setup progress (roadmap 25e, ADR-0015)."""

import datetime as dt

from app.schemas.common import Schema


class SetupProgressOut(Schema):
    finished_at: dt.datetime | None = None
    phrase_saved_at: dt.datetime | None = None
    last_backup_at: dt.datetime | None = None  # read-only: set when a backup file is written


class SetupProgressIn(Schema):
    """Only the fields sent change. True stamps the time now (once); False clears it."""

    finished: bool | None = None
    phrase_saved: bool | None = None
