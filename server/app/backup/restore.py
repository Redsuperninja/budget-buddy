"""Restoring a backup: check all of it into a staging folder first, then swap it in (ADR-0012).

The swap only happens while no Home Base runs on the folder (it holds ``run_lock``). The current
data moves to a ``before-restore-<date-time>`` folder in the data folder and is never deleted.
Phones and computers removed since the backup was made stay removed.
"""

import json
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app import run_lock
from app.backup.archive import BackupContentsError, extract_backup
from app.crypto import database_has_rows
from app.crypto._fs import ensure_private_dir
from app.crypto.errors import DecryptionError
from app.crypto.files import RECEIPTS_DIRNAME
from app.crypto.keys import (
    FINGERPRINT_FILENAME,
    PURPOSE_BACKUP,
    derive_key,
    fingerprint,
    save_fingerprint,
)
from app.crypto.stream import read_header
from app.db import (
    DB_FILENAME,
    NEWER_DATABASE_MESSAGE,
    _exclusive_lock,
    database_revision,
    known_revisions,
    open_read_only,
)
from app.instance_proof import FILE_NAME as RUNNING_FILE
from app.parent_watch import process_alive
from app.services.devices.pairing_sessions import SERVER_ID_FILENAME

STAGING_PREFIX = ".restore-"
COPY_PREFIX = ".backup-"  # temporary database copies and dashboard downloads
BEFORE_PREFIX = "before-restore-"
STALE_SECONDS = 3600
# What a restore replaces. Keys, lock files and older .bak copies stay as they are.
REPLACED = (
    DB_FILENAME,
    f"{DB_FILENAME}-wal",
    f"{DB_FILENAME}-shm",
    SERVER_ID_FILENAME,
    RECEIPTS_DIRNAME,
)
CLOSE_FIRST = "Budget Buddy is running. Close it first, then restore."


@dataclass(frozen=True)
class BackupKey:
    """What opening a backup needs: which master key it must be (fingerprint) and its backup
    subkey. The running Home Base has these without ever holding the master key."""

    fingerprint: str
    backup: bytes = field(repr=False)

    @classmethod
    def from_master(cls, master_key: bytes) -> "BackupKey":
        return cls(fingerprint(master_key), derive_key(master_key, PURPOSE_BACKUP))


class RestoreError(RuntimeError):
    """A backup can't be restored here. The message is meant for the person."""


class RestoreStuckError(RestoreError):
    """A swap failed and couldn't be fully undone: keep every folder as it is."""


def backup_fingerprint(path: Path) -> str:
    """Which key made the backup at ``path`` (the fingerprint in its header)."""
    try:
        with open(path, "rb") as source:
            return read_header(source)[0]
    except OSError as exc:
        raise RestoreError(f"Couldn't open {path}: {exc.strerror or exc}.") from exc


def home_base_running(data_dir: Path) -> bool:
    try:
        pid = json.loads((data_dir / RUNNING_FILE).read_text(encoding="ascii"))["pid"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return isinstance(pid, int) and process_alive(pid)


# Tables a new Budget Buddy already fills (default categories, nothing encrypted), so rows there
# don't count as data of the folder's own.
_STARTER_TABLES = frozenset({"categories"})  # a new Home Base fills it with defaults


def has_own_data(data_dir: Path) -> bool:
    """True if the folder holds anything a key change would make unreadable: rows of the
    person's own, receipt files, an earlier restore's set-aside data or an update's ``.bak``
    copy. A newly started Budget Buddy (default categories only) has none."""
    receipts = data_dir / RECEIPTS_DIRNAME
    return (
        database_has_rows(data_dir, ignore=_STARTER_TABLES)
        or (receipts.is_dir() and any(receipts.iterdir()))
        or any(data_dir.glob(f"{BEFORE_PREFIX}*"))
        or any(data_dir.glob(f"{DB_FILENAME}.bak-*"))
    )


def sweep_leftovers(data_dir: Path) -> None:
    """Delete staging folders and database copies left by a backup or restore that was cut
    short (an hour old or more, so one still running is left alone)."""
    cutoff = time.time() - STALE_SECONDS
    for path in [*data_dir.glob(f"{STAGING_PREFIX}*"), *data_dir.glob(f"{COPY_PREFIX}*")]:
        try:
            if path.stat().st_mtime < cutoff:
                shutil.rmtree(path) if path.is_dir() else path.unlink()
        except OSError:
            pass  # tried again next start


def _check_database(db_path: Path) -> None:
    try:
        with open_read_only(db_path) as connection:
            ok = connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    except sqlite3.DatabaseError:
        ok = False
    if not ok:
        raise RestoreError("The database inside that backup is damaged.")
    revision = database_revision(db_path)
    if revision is None:
        raise RestoreError("That backup's database isn't from Budget Buddy.")
    if revision not in known_revisions():
        raise RestoreError(NEWER_DATABASE_MESSAGE)


def check_backup(path: Path, data_dir: Path, key: BackupKey) -> tuple[Path, dict]:
    """Decrypt and check all of the backup at ``path`` into a new staging folder inside
    ``data_dir``. Returns (staging folder, manifest). Nothing in the data folder changes."""
    if not path.is_file():
        raise RestoreError(f"There's no file at {path}.")
    staging = data_dir / f"{STAGING_PREFIX}{uuid.uuid4().hex}"
    ensure_private_dir(staging)
    try:
        with open(path, "rb") as source:
            made_by, salt, header = read_header(source)
            if made_by != key.fingerprint:
                raise RestoreError("That backup was made with a different key.")
            manifest = extract_backup(source, key.backup, salt, header, staging)
        _check_database(staging / DB_FILENAME)
        return staging, manifest
    except (DecryptionError, BackupContentsError) as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise RestoreError(str(exc)) from exc
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _tables(connection: sqlite3.Connection, kind: str = "table") -> set[str]:
    query = "SELECT name FROM sqlite_master WHERE type = ?"
    return {name for (name,) in connection.execute(query, (kind,))}


def carry_over_removals(old_db: Path, new_db: Path) -> None:
    """Phones and computers removed in ``old_db`` (the data being replaced) are removed in
    ``new_db`` too, so restoring an older backup can't let a lost phone sync again."""
    if not old_db.is_file():
        return
    with open_read_only(old_db) as old:
        tables = _tables(old)
        phones, computers = [], []
        if "devices" in tables:
            phones = old.execute(
                "SELECT token_hash, revoked_at FROM devices WHERE revoked"
            ).fetchall()
        if "remote_computers" in tables:
            computers = old.execute(
                "SELECT id, paired_at, revoked_at FROM remote_computers "
                "WHERE revoked_at IS NOT NULL"
            ).fetchall()
    connection = sqlite3.connect(new_db)
    try:
        tables = _tables(connection)
        with connection:
            if "devices" in tables:
                connection.executemany(
                    "UPDATE devices SET revoked = 1, revoked_at = COALESCE(revoked_at, ?), "
                    "sync_key = NULL WHERE token_hash = ?",
                    [(revoked_at, token_hash) for token_hash, revoked_at in phones],
                )
            if "remote_computers" in tables:
                connection.executemany(
                    "UPDATE remote_computers SET token_hash = NULL, "
                    "revoked_at = COALESCE(revoked_at, ?) WHERE id = ? AND paired_at = ?",
                    [(revoked_at, id_, paired_at) for id_, paired_at, revoked_at in computers],
                )
    finally:
        connection.close()


def _new_before_folder(data_dir: Path) -> Path:
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    for attempt in range(100):
        before = data_dir / (f"{BEFORE_PREFIX}{stamp}" + (f"-{attempt + 1}" if attempt else ""))
        try:
            before.mkdir(mode=0o700)
        except FileExistsError:
            continue
        ensure_private_dir(before)
        return before
    raise RestoreError("Couldn't make a folder for your current data.")


def _swap(data_dir: Path, staging: Path, before: Path) -> None:
    moves: list[tuple[Path, Path]] = []  # (from, to), to undo if something fails half-way
    try:
        for name in REPLACED:
            if (data_dir / name).exists():
                (data_dir / name).rename(before / name)
                moves.append((data_dir / name, before / name))  # only once it has happened
        for item in list(staging.iterdir()):
            item.rename(data_dir / item.name)
            moves.append((item, data_dir / item.name))
    except OSError as exc:
        stuck = []
        for source, target in reversed(moves):
            try:
                target.rename(source)
            except OSError:
                stuck.append(f"{target} (belongs at {source})")
        if stuck:
            raise RestoreStuckError(
                "The restore stopped half-way and couldn't put everything back. Nothing was "
                "deleted. Close Budget Buddy and anything using the data folder, then move these "
                "back by hand: " + "; ".join(stuck)
            ) from exc
        raise RestoreError(
            "Couldn't swap in the backup, so your data was put back as it was. Close anything "
            f"using the data folder ({exc.strerror or exc}), then try again."
        ) from exc


def apply_restore(data_dir: Path, staging: Path, fingerprint_hex: str) -> Path:
    """Move the current data aside and the checked backup in. Returns the folder the old data
    is in. Deletes ``staging`` unless a failed swap couldn't be undone (RestoreStuckError). The
    key goes into the password vault afterwards (the caller's job)."""
    lock = run_lock.try_lock(data_dir)
    if lock is None or home_base_running(data_dir):
        if lock:
            run_lock.release(lock)
        raise RestoreError(CLOSE_FIRST)
    try:
        # Also wait out a Home Base that is still starting (it migrates under this lock).
        with _exclusive_lock(data_dir / f"{DB_FILENAME}.lock"):
            carry_over_removals(data_dir / DB_FILENAME, staging / DB_FILENAME)
            before = _new_before_folder(data_dir)
            old_fingerprint = data_dir / FINGERPRINT_FILENAME
            if old_fingerprint.is_file():  # says which recovery phrase opens the old data
                shutil.copy2(old_fingerprint, before / FINGERPRINT_FILENAME)
            try:
                _swap(data_dir, staging, before)
            except RestoreStuckError:
                raise
            except RestoreError:
                shutil.rmtree(staging, ignore_errors=True)  # everything is back where it was
                shutil.rmtree(before, ignore_errors=True)
                raise
            staging.rmdir()
            save_fingerprint(data_dir, fingerprint_hex)
            return before
    finally:
        run_lock.release(lock)
