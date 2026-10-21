"""Command-line backups: ``python -m app backup make [--to FOLDER]`` and ``backup restore FILE``
(ADR-0012). The dashboard offers the same; this works when the Home Base can't start."""

import datetime as dt
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from app import __version__
from app.backup.archive import BackupError, write_backup
from app.backup.restore import (
    CLOSE_FIRST,
    BackupKey,
    RestoreError,
    RestoreStuckError,
    apply_restore,
    backup_fingerprint,
    check_backup,
    has_own_data,
    home_base_running,
)
from app.config import Settings
from app.crypto import (
    DerivedKeys,
    EncryptionError,
    FieldCipher,
    get_key_store,
    key_name_for,
    phrase_to_master_key,
)
from app.crypto.keys import (
    MISSING_KEY_MESSAGE,
    WRONG_KEY_MESSAGE,
    fingerprint,
    load_master_key,
    matches_fingerprint,
    read_fingerprint,
)
from app.db import create_db_engine, database_path

Output = Callable[[str], None]
Input = Callable[[str], str]
SUFFIX = ".bbbackup"

SAVE_IT_SAFELY = (
    "Copy it somewhere other than this computer, like a USB drive. It's encrypted: it opens only "
    "on this computer, or with your recovery phrase (python -m app recovery-phrase show)."
)


def default_backup_folder() -> Path:
    documents = Path.home() / "Documents"
    return documents if documents.is_dir() else Path.home()


def backup_name(folder: Path, today: dt.datetime) -> Path:
    """``budget-buddy-backup-<date>.bbbackup``, with the time added if that name is taken."""
    path = folder / f"budget-buddy-backup-{today:%Y-%m-%d}{SUFFIX}"
    return (
        path
        if not path.exists()
        else folder / f"budget-buddy-backup-{today:%Y-%m-%d-%H%M%S}{SUFFIX}"
    )


def make_backup(settings: Settings, folder: Path | None, output: Output = print) -> int:
    data_dir = settings.data_dir
    if not database_path(data_dir).is_file():
        output(f"There's no Budget Buddy data in {data_dir} to back up yet.")
        return 1
    key = load_master_key(get_key_store(settings.key_store), data_dir)
    if key is None or matches_fingerprint(data_dir, key) is False:
        message = MISSING_KEY_MESSAGE if key is None else WRONG_KEY_MESSAGE
        output(message.format(data_dir=data_dir))
        return 1
    folder = folder or default_backup_folder()
    if not folder.is_dir():
        output(f"There's no folder at {folder}.")
        return 1
    target = backup_name(folder, dt.datetime.now())
    partial = target.with_name(target.name + ".partial")
    keys = DerivedKeys.from_master(key)
    engine = create_db_engine(
        data_dir,
        field_cipher=FieldCipher(keys.db_fields),
        database_key=keys.db_file if settings.database_encryption else None,
    )
    try:
        # Owner-only on macOS/Linux, like everything in the data folder (it's encrypted anyway).
        fd = os.open(
            partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600
        )
        with os.fdopen(fd, "wb") as out:
            manifest = write_backup(
                out, data_dir, engine, keys.backup, fingerprint(key), __version__
            )
            out.flush()
            os.fsync(out.fileno())
        os.replace(partial, target)
    except BackupError as exc:
        partial.unlink(missing_ok=True)
        output(str(exc))
        return 1
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    finally:
        engine.dispose()
    output(f"Backup saved: {target} ({manifest['receipts']} receipt photos included).")
    output(SAVE_IT_SAFELY)
    return 0


def describe(manifest: dict) -> str:
    """``made 2026-10-16 14:05, with 3 receipt photos``, without trusting the manifest's types."""
    try:
        made = dt.datetime.fromtimestamp(int(manifest.get("created"))).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OverflowError, OSError):
        made = "on an unknown date"
    receipts = manifest.get("receipts")
    count = receipts if isinstance(receipts, int) and receipts >= 0 else 0
    return f"made {made}, with {count} receipt photos"


def _key_for(settings: Settings, file: Path, output: Output, ask_secret: Input) -> bytes | None:
    """The master key that made ``file``: this folder's, or the recovery phrase typed for it."""
    made_by = backup_fingerprint(file)
    current = load_master_key(get_key_store(settings.key_store), settings.data_dir)
    if current is not None and fingerprint(current) == made_by:
        return current
    output(
        "This backup was made with a different encryption key (on another computer, or before a "
        "reinstall). Type the recovery phrase from when it was made. For privacy, what you type "
        "won't appear on the screen."
    )
    key = phrase_to_master_key(ask_secret("Recovery phrase: "))
    if fingerprint(key) != made_by:
        output("That recovery phrase is valid, but it isn't the one this backup was made with.")
        return None
    folder_key = read_fingerprint(settings.data_dir) or (current and fingerprint(current))
    if folder_key and folder_key != made_by and has_own_data(settings.data_dir):
        output(
            f"{settings.data_dir} already holds data under a different key, and restoring would "
            "make it unreadable. Restore into an empty folder instead (set BUDGET_BUDDY_DATA_DIR)."
        )
        return None
    return key


def restore_backup(
    settings: Settings, file: Path, output: Output, ask: Input, ask_secret: Input
) -> int:
    data_dir = settings.data_dir
    if home_base_running(data_dir):
        output(CLOSE_FIRST)
        return 1
    try:
        key = _key_for(settings, file, output, ask_secret)
        if key is None:
            output("Nothing was changed.")
            return 1
        from app.main import ensure_data_dir

        ensure_data_dir(data_dir)
        output("Checking the whole backup first...")
        staging, manifest = check_backup(file, data_dir, BackupKey.from_master(key))
    except RestoreError as exc:
        output(f"{exc} Nothing was changed.")
        return 1
    keep_staging = False  # only when a failed swap couldn't be undone: files are still in it
    try:
        output(f"The backup is fine: {describe(manifest)}.")
        if has_own_data(data_dir):
            answer = ask(
                "Your current data will be moved to a 'before-restore' folder inside the data "
                "folder (not deleted). Type RESTORE to continue, or press Enter to cancel: "
            )
            if answer.strip() != "RESTORE":
                output("Cancelled. Nothing was changed.")
                return 1
        try:
            before = apply_restore(data_dir, staging, fingerprint(key))
        except RestoreStuckError as exc:
            keep_staging = True
            output(str(exc))
            return 1
        except RestoreError as exc:
            output(f"{exc} Nothing was changed.")
            return 1
    finally:
        if not keep_staging:
            shutil.rmtree(staging, ignore_errors=True)
    store = get_key_store(settings.key_store)
    if store.get(key_name_for(data_dir)) != key:
        try:
            store.set(key_name_for(data_dir), key)
        except EncryptionError:
            output(
                f"Restored, and your data from before is in {before}, but the key couldn't be "
                "saved in this computer's password vault. Run: python -m app recovery-phrase "
                "restore, and type the same recovery phrase."
            )
            return 1
    output(f"Restored. Your data from before is in {before}. Start Budget Buddy as usual.")
    return 0
