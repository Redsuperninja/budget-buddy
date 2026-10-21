"""The dashboard's backups (roadmap 24b): make one to download, or check an uploaded one so the
next start can swap it in (``pending.py``). The same checks as the command line (ADR-0012)."""

import datetime as dt
import os
import uuid
from pathlib import Path

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Engine

from app import __version__
from app.backup import pending
from app.backup.archive import BackupError, write_backup
from app.backup.restore import (
    STAGING_PREFIX,
    BackupKey,
    RestoreError,
    backup_fingerprint,
    check_backup,
    has_own_data,
)
from app.bodylimit import too_large
from app.crypto import DerivedKeys, KeyStore, phrase_to_master_key
from app.crypto.errors import DecryptionError, RecoveryPhraseError
from app.crypto.keys import fingerprint, read_fingerprint
from app.db import make_private_file
from app.errors import ApiError
from app.services.setup_progress import record_backup

UPLOAD_LIMIT_BYTES = 4 * 1024**3  # far more than years of data and receipt photos
DOWNLOAD_PREFIX = ".backup-"  # swept at start-up like the other leftovers


def download_name(today: dt.date) -> str:
    return f"budget-buddy-backup-{today:%Y-%m-%d}.bbbackup"


def make_download(data_dir: Path, engine: Engine, keys: DerivedKeys) -> Path:
    """Write a backup into the data folder for the browser to download. The caller deletes it."""
    made_by = read_fingerprint(data_dir)
    path = data_dir / f"{DOWNLOAD_PREFIX}{uuid.uuid4().hex}.bbbackup"
    make_private_file(path)
    try:
        with open(path, "r+b") as out:
            write_backup(out, data_dir, engine, keys.backup, made_by, __version__)
    except BackupError as exc:
        path.unlink(missing_ok=True)
        raise ApiError(409, "backup_not_ready", str(exc)) from exc
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def send_and_delete(path: Path, chunk_size: int = 1024 * 1024, engine: Engine | None = None):
    """The file's bytes for a download; deleted when sent, or when the browser stops early.
    With an ``engine``, the last-backup date is noted only once the last chunk went out."""
    try:
        with open(path, "rb") as source:
            while chunk := source.read(chunk_size):
                yield chunk
        if engine is not None:
            record_backup(engine)
    finally:
        path.unlink(missing_ok=True)


async def receive_upload(request: Request, data_dir: Path) -> Path:
    """Save the request body to a private file in the data folder, stopping over the limit."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > UPLOAD_LIMIT_BYTES:
        raise too_large()
    path = data_dir / f"{STAGING_PREFIX}upload-{uuid.uuid4().hex}.bbbackup"
    make_private_file(path)
    size = 0
    try:
        with open(path, "r+b") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > UPLOAD_LIMIT_BYTES:
                    raise too_large()
                await run_in_threadpool(out.write, chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _key_for(upload: Path, data_dir: Path, keys: DerivedKeys, phrase: str | None) -> tuple:
    """(BackupKey, the master key to keep for the next start or None) for the uploaded file."""
    made_by = backup_fingerprint(upload)
    if made_by == read_fingerprint(data_dir):
        return BackupKey(made_by, keys.backup), None
    if not phrase:
        raise ApiError(
            409,
            "recovery_phrase_needed",
            "This backup was made with a different key (on another computer, or before a "
            "reinstall). Type the recovery phrase from when it was made.",
        )
    try:
        master_key = phrase_to_master_key(phrase)
    except RecoveryPhraseError as exc:
        raise ApiError(422, "recovery_phrase_invalid", str(exc)) from exc
    if fingerprint(master_key) != made_by:
        raise ApiError(
            422,
            "recovery_phrase_mismatch",
            "That recovery phrase is valid, but it isn't the one this backup was made with.",
        )
    if has_own_data(data_dir):
        raise ApiError(
            409,
            "different_key_data",
            "Budget Buddy on this computer already has data of its own under a different key, "
            "and restoring this backup would make that data unreadable. Nothing was changed.",
        )
    return BackupKey.from_master(master_key), master_key


def check_upload(
    upload: Path, data_dir: Path, keys: DerivedKeys, store: KeyStore, phrase: str | None
) -> dict:
    """Check all of an uploaded backup and keep it for the next start. Deletes the upload."""
    try:
        key, master_key = _key_for(upload, data_dir, keys, phrase)
        staging, manifest = check_backup(upload, data_dir, key)
        return pending.stage(data_dir, staging, manifest, key, store, master_key)
    except (RestoreError, DecryptionError) as exc:
        raise ApiError(422, "backup_unusable", f"{exc} Nothing was changed.") from exc
    finally:
        try:
            os.unlink(upload)
        except OSError:
            pass  # swept at the next start
