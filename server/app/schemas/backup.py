"""Backups in the dashboard (roadmap 24b)."""

from pydantic import BaseModel


class PendingRestore(BaseModel):
    """A checked backup waiting for the next start."""

    fingerprint: str
    made: int | None = None  # Unix seconds, from the backup's manifest
    receipts: int | None = None


class BackupStatus(BaseModel):
    key_fingerprint: str | None  # which key this folder's backups are made with (not a secret)
    pending: PendingRestore | None
    restored_from: str | None  # set once, on the start that finished a restore
