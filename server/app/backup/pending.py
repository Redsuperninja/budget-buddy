"""A restore the dashboard has checked, finished the next time Budget Buddy starts (ADR-0012).

A running Home Base can't swap its own files, so the dashboard checks the whole backup into
``restore-pending/`` (with ``restore-pending.json``: which key, when it was made, how many receipt
photos) and asks the person to restart. The next start swaps it in before opening the database,
renaming the info file to ``restore-swapping.json`` first so a start cut short can tell.
A backup made with another key (a new computer) needs its master key then: it waits in the
password vault under its own name, never in a file, and is removed once used or cancelled.
"""

import json
import logging
import shutil
from pathlib import Path

from pydantic import ValidationError

from app.backup.restore import (
    BackupKey,
    RestoreError,
    RestoreStuckError,
    apply_restore,
    has_own_data,
)
from app.crypto._fs import write_private_bytes
from app.crypto.keys import fingerprint, read_fingerprint, save_fingerprint
from app.crypto.keystore import KeyStore, key_name_for
from app.schemas.backup import PendingRestore

logger = logging.getLogger(__name__)

PENDING_DIR = "restore-pending"
PENDING_INFO = "restore-pending.json"
SWAPPING_INFO = "restore-swapping.json"  # the swap has started: never start it again
CUT_SHORT = (
    "Budget Buddy was stopped in the middle of restoring a backup, so the data folder is "
    "incomplete. Nothing was deleted: your earlier data is in a before-restore folder and the "
    "rest of the backup is in restore-pending, both in {data_dir}. Get help putting them back "
    "before using Budget Buddy."
)


def _pending_key_name(data_dir: Path) -> str:
    return key_name_for(data_dir) + "-restore"


def pending(data_dir: Path) -> dict | None:
    """What's waiting (``fingerprint``, ``made``, ``receipts``), or None."""
    try:
        info = json.loads((data_dir / PENDING_INFO).read_text(encoding="ascii"))
    except (OSError, ValueError):
        return None
    try:
        info = PendingRestore.model_validate(info).model_dump()
    except ValidationError:
        return None
    return info if (data_dir / PENDING_DIR).is_dir() else None


def cancel(data_dir: Path, store: KeyStore) -> None:
    """Forget a waiting restore. Nothing else changes."""
    (data_dir / PENDING_INFO).unlink(missing_ok=True)
    shutil.rmtree(data_dir / PENDING_DIR, ignore_errors=True)
    store.delete(_pending_key_name(data_dir))


def stage(
    data_dir: Path,
    staging: Path,
    manifest: dict,
    key: BackupKey,
    store: KeyStore,
    new_master_key: bytes | None = None,
) -> dict:
    """Keep a checked staging folder (from ``check_backup``) for the next start. ``new_master_key``
    is the key a backup from another computer needs. Replaces any restore already waiting."""
    cancel(data_dir, store)
    info = {
        "fingerprint": key.fingerprint,
        "made": manifest.get("created"),
        "receipts": manifest.get("receipts"),
    }
    try:
        if new_master_key is not None:
            store.set(_pending_key_name(data_dir), new_master_key)
        staging.rename(data_dir / PENDING_DIR)
        write_private_bytes(data_dir / PENDING_INFO, json.dumps(info).encode("ascii"))
    except BaseException:
        cancel(data_dir, store)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return info


def _store_key(data_dir: Path, store: KeyStore, made_by: str) -> None:
    """After a swap: the waiting key (if any) becomes the folder's key, then the marker goes."""
    new_key = store.get(_pending_key_name(data_dir))
    if new_key is not None and fingerprint(new_key) == made_by:
        store.set(key_name_for(data_dir), new_key)
    store.delete(_pending_key_name(data_dir))
    (data_dir / SWAPPING_INFO).unlink(missing_ok=True)


def _resume(data_dir: Path, store: KeyStore) -> None:
    """A start that was cut short during a restore. If the swap got to the end, finish the last
    steps; otherwise stop, since the data folder is half old and half new."""
    try:
        made_by = json.loads((data_dir / SWAPPING_INFO).read_text(encoding="ascii"))["fingerprint"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RestoreStuckError(CUT_SHORT.format(data_dir=data_dir)) from exc
    if (data_dir / PENDING_DIR).exists():
        raise RestoreStuckError(CUT_SHORT.format(data_dir=data_dir))
    save_fingerprint(data_dir, made_by)  # the swap's last step, in case it was missed
    _store_key(data_dir, store, made_by)
    logger.warning("Budget Buddy finished restoring your backup after being stopped part-way.")


def finish(data_dir: Path, store: KeyStore) -> Path | None:
    """At start-up, before the database is opened: swap in a waiting restore. Returns the folder
    the replaced data was moved to, or None if nothing was waiting (or it couldn't be used, in
    which case it's cancelled and logged). A swap that fails or was cut short half-way stops the
    start (RestoreStuckError), since the data folder is then incomplete."""
    if (data_dir / SWAPPING_INFO).exists():
        _resume(data_dir, store)
        return None
    info = pending(data_dir)
    if info is None:
        if (data_dir / PENDING_DIR).exists() or (data_dir / PENDING_INFO).exists():
            cancel(data_dir, store)  # half of one: never usable
        return None
    made_by = info["fingerprint"]
    if made_by != read_fingerprint(data_dir):
        new_key = store.get(_pending_key_name(data_dir))
        if new_key is None or fingerprint(new_key) != made_by or has_own_data(data_dir):
            logger.warning(
                "Budget Buddy couldn't finish the restore you started: the backup was made with "
                "a different key, and this data folder now has data of its own (or the key is "
                "missing). Your data wasn't changed. Start the restore again from Backups."
            )
            cancel(data_dir, store)
            return None
    (data_dir / PENDING_INFO).replace(data_dir / SWAPPING_INFO)
    try:
        before = apply_restore(data_dir, data_dir / PENDING_DIR, made_by)
    except RestoreStuckError:
        raise  # stuck half-way: keep everything as it is (the message says what to do)
    except RestoreError as exc:
        logger.warning("Budget Buddy couldn't finish the restore you started: %s", exc)
        (data_dir / SWAPPING_INFO).replace(data_dir / PENDING_INFO)  # nothing was moved
        if not (data_dir / PENDING_DIR).exists():  # the failed swap was undone and tidied
            cancel(data_dir, store)
        return None  # otherwise (another copy running on this folder) it waits for next time
    _store_key(data_dir, store, made_by)
    logger.warning("Budget Buddy restored your backup. Your data from before is in %s.", before)
    return before
