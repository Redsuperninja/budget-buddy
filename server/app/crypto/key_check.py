"""Check a master key against the encrypted values already in ``budget.db`` (issue #26).

The ``key-fingerprint`` file is the quick check, but it's only a file: it can be deleted, or
missing from an older copy of the folder. The database itself is the real proof. If it holds an
encrypted value, only the right key can decrypt it.
"""

import sqlite3
from pathlib import Path

from app.crypto import sqlcipher
from app.crypto.errors import DecryptionError, KeyCheckError, WrongKeyError
from app.crypto.fields import FIELD_FORMAT_V1, EncryptedString, FieldCipher
from app.crypto.keys import PURPOSE_DB_FIELDS, PURPOSE_DB_FILE, derive_key

SAMPLES_PER_COLUMN = 3  # a few, so one damaged value can't lock out the right key

UNREADABLE_MESSAGE = (
    "Budget Buddy couldn't read the database in {data_dir} to check that the encryption key "
    "belongs to it, so it stopped before changing anything. If another copy of Budget Buddy "
    "is running, close it and try again."
)


def _encrypted_columns() -> list[tuple[str, str, str]]:
    """(table, column, context) for every encrypted column the app knows about."""
    from app.models import Base  # imported here: the models import this package

    return [
        (table.name, column.name, column.type.context)
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if isinstance(column.type, EncryptedString)
    ]


def _is_missing_table_or_column(exc: Exception) -> bool:
    """True for SQLite's and SQLCipher's "no such table/column" (their error classes differ)."""
    return str(exc).startswith(("no such table", "no such column"))


def encrypted_samples(data_dir: Path, database_key: bytes | None = None) -> list[tuple[bytes, str]]:
    """A few encrypted values from ``budget.db`` with their contexts (empty if there are none).

    Skips text left in a column from before it was encrypted (migration 0003 not run yet), and
    tables or columns an older database doesn't have yet. Raises ``KeyCheckError`` if the
    database can't be read, so an unreadable file never counts as "nothing to check".
    ``database_key`` opens an encrypted database; its wrong-key, busy and damaged errors are
    raised as they are.
    """
    from app.db import open_read_only  # imported here: app.db imports this package

    path = data_dir / "budget.db"
    if not path.is_file() or path.stat().st_size == 0:
        return []
    samples: list[tuple[bytes, str]] = []
    try:
        with open_read_only(path, database_key) as connection:
            for table, column, context in _encrypted_columns():
                try:
                    rows = connection.execute(
                        f'SELECT "{column}" FROM "{table}" WHERE typeof("{column}") = \'blob\' '
                        f'AND substr("{column}", 1, 1) = ? LIMIT ?',
                        (bytes([FIELD_FORMAT_V1]), SAMPLES_PER_COLUMN),
                    ).fetchall()
                except Exception as exc:
                    if not _is_missing_table_or_column(exc):
                        raise
                    continue
                samples.extend((bytes(value), context) for (value,) in rows)
    except sqlite3.DatabaseError as exc:
        raise KeyCheckError(UNREADABLE_MESSAGE.format(data_dir=data_dir)) from exc
    except Exception as exc:
        if database_key is None:
            raise
        raise sqlcipher.classify_error(exc) from None  # wrong key, busy or damaged, separately
    return samples


def _encrypted_database_opens(data_dir: Path, master_key: bytes) -> bool | None:
    """Opening the file with the database key is the check (ADR-0014): False for a wrong key,
    ``None`` for a new, empty file, and busy or damaged files raise their own errors."""
    path = data_dir / "budget.db"
    if not path.is_file() or path.stat().st_size == 0:
        return None
    from app.db import open_read_only  # imported here: app.db imports this package

    try:
        with open_read_only(path, derive_key(master_key, PURPOSE_DB_FILE)):
            return True
    except WrongKeyError:
        return False


def key_opens_database(
    data_dir: Path, master_key: bytes, database_encryption: bool = False
) -> bool | None:
    """True if the key decrypts any sampled value, False if it decrypts none, ``None`` if the
    database has no encrypted value to try. With ``database_encryption`` the whole file is
    encrypted, so the check is whether the database key opens it."""
    if database_encryption:
        return _encrypted_database_opens(data_dir, master_key)
    samples = encrypted_samples(data_dir)
    if not samples:
        return None
    cipher = FieldCipher(derive_key(master_key, PURPOSE_DB_FIELDS))
    for blob, context in samples:
        try:
            cipher.decrypt(blob, context)
        except DecryptionError:
            continue
        return True
    return False
