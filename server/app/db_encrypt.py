"""Move an existing plain ``budget.db`` into a SQLCipher file, once (ADR-0014, requirement 5).

Order matters, because a crash can happen between any two steps and no plain copy may be kept:
write the ``encrypt-pending`` marker, empty the write-ahead log, export to ``budget.db.encrypting``,
prove the copy opens with the key and holds the same rows, delete the plain ``-wal`` and ``-shm``
(they are empty by then, and a stale one must never meet the new file), swap the new file in, then
clear the marker. A start that finds the marker begins again from the plain file, or just clears
the marker if the swap had already happened. There is no plain fallback: if any step fails the
plain file is left as it was and the start stops with a plain-English error.
"""

import logging
import sqlite3
from pathlib import Path

from app.crypto import sqlcipher
from app.crypto._fs import write_private_bytes
from app.crypto.errors import MOVE_FAILED_MESSAGE, DatabaseMoveError, EncryptionError
from app.db import _exclusive_lock, make_private_file

logger = logging.getLogger(__name__)

PENDING_MARKER = "encrypt-pending"
NEW_SUFFIX = ".encrypting"
SIDECARS = ("-wal", "-shm", "-journal")


def _remove_new(new: Path) -> None:
    for suffix in ("", *SIDECARS):
        new.with_name(new.name + suffix).unlink(missing_ok=True)


def _is_plain(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _counts(connection) -> dict[str, int]:
    names = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {n: connection.execute(f"SELECT count(*) FROM {_quote(n)}").fetchone()[0] for n in names}


def _export(plain: Path, new: Path, key: bytes) -> None:
    """Checkpoint the plain file, then write an encrypted copy of it (with ``user_version``)."""
    with sqlite3.connect(plain) as check:  # a plain connection empties the log into the file
        busy = check.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
        # Leaving WAL mode needs the only connection: it fails if another copy is open, and
        # removes the log itself, so nothing can write to the plain file from here on.
        mode = check.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        if busy or mode.lower() != "delete":
            raise DatabaseMoveError(MOVE_FAILED_MESSAGE)
        version = check.execute("PRAGMA user_version").fetchone()[0]
    check.close()
    make_private_file(new)
    module = sqlcipher.dbapi_module()
    connection = module.connect(str(plain))
    try:
        # The key is bound (never in SQL text); a raw key is written as x'<hex>'.
        connection.execute("ATTACH DATABASE ? AS encrypted KEY ?", (str(new), f"x'{key.hex()}'"))
        connection.execute("SELECT sqlcipher_export('encrypted')").fetchall()
        connection.execute(f"PRAGMA encrypted.user_version = {int(version)}")
        connection.commit()
        connection.execute("DETACH DATABASE encrypted")
    finally:
        connection.close()


def _verify(plain: Path, new: Path, key: bytes) -> None:
    """The new file opens with the key and holds the same tables and row counts."""
    with sqlite3.connect(f"{plain.resolve().as_uri()}?mode=ro", uri=True) as source:
        expected = _counts(source)
        version = source.execute("PRAGMA user_version").fetchone()[0]
    source.close()
    target = sqlcipher.connect(new, key, read_only=True)
    try:
        if _counts(target) != expected:
            raise DatabaseMoveError(MOVE_FAILED_MESSAGE)
        if target.execute("PRAGMA user_version").fetchone()[0] != version:
            raise DatabaseMoveError(MOVE_FAILED_MESSAGE)
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise DatabaseMoveError(MOVE_FAILED_MESSAGE)
    finally:
        target.close()


def plain_backups(db_path: Path) -> list[Path]:
    """Every older ``budget.db.bak-*`` copy that is still plain SQLite."""
    return [b for b in sorted(db_path.parent.glob(f"{db_path.name}.bak-*")) if _is_plain(b)]


def encrypt_existing_database(db_path: Path, key: bytes) -> bool:
    """Move a plain database to SQLCipher. True if it moved (or finished a half-done move).

    Does nothing for a new, empty or already encrypted database.
    """
    marker = db_path.with_name(PENDING_MARKER)
    new = db_path.with_name(db_path.name + NEW_SUFFIX)
    with _exclusive_lock(db_path.with_name(db_path.name + ".lock")):
        if not _is_plain(db_path):
            leftover = marker.exists()
            _remove_new(new)  # an unfinished export is never trusted
            marker.unlink(missing_ok=True)  # the swap had happened; only the marker was left
            return leftover
        write_private_bytes(marker, b"")
        _remove_new(new)
        try:
            _export(db_path, new, key)
            _verify(db_path, new, key)
            for suffix in SIDECARS:
                db_path.with_name(db_path.name + suffix).unlink(missing_ok=True)
            new.replace(db_path)  # atomic: the plain file is gone from the name in one step
        except EncryptionError:
            _remove_new(new)
            raise
        except Exception as exc:
            _remove_new(new)
            logger.warning("Moving the database into the encrypted form failed.", exc_info=True)
            raise DatabaseMoveError(MOVE_FAILED_MESSAGE) from exc
        marker.unlink(missing_ok=True)
    old = plain_backups(db_path)
    if old:
        logger.warning(
            "Budget Buddy's database is now encrypted. These older backup copies were made "
            "before that and are NOT encrypted: %s. Once you've checked Budget Buddy is "
            "working, delete them (or keep them somewhere safe). The old unencrypted "
            "database file may also survive in free disk space or in OneDrive versions.",
            ", ".join(str(b) for b in old),
        )
    return True
