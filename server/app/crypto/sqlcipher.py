"""Open a database file with SQLCipher, keyed with a raw 256-bit key (ADR-0014).

The key is set only on the raw DB-API cursor, as the very first statement of a new connection.
Nothing here puts it in a URL, an SQLAlchemy statement, a log line or an exception message: the
hex string is built inside ``open_with_key`` and dropped. (A Python string can't be wiped from
memory; the field keys are the same.)
"""

import re
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, event

from app.crypto.errors import CipherProviderError, UnencryptedDatabaseError, WrongKeyError

DATABASE_KEY_BYTES = 32
# SQLCipher links its own OpenSSL, so a fix reaches us only with a new ``sqlcipher3`` wheel.
# Refuse an older one at start (ADR-0014, L6). 3.5 is the oldest OpenSSL long-term-support line.
MIN_PROVIDER_VERSION = (3, 5, 0)

WRONG_KEY_MESSAGE = (
    "The encryption key on this computer can't open Budget Buddy's database, so it stopped "
    "before changing anything. If you saved your recovery phrase for this folder, run:  "
    "python -m app recovery-phrase restore"
)
OLD_PROVIDER_MESSAGE = (
    "The database encryption library inside this copy of Budget Buddy is too old to be "
    "trusted. Update Budget Buddy (in the launch folder, double-click Build desktop app, then "
    "Install desktop app). Your data is safe and unchanged."
)

PLAIN_DATABASE_MESSAGE = (
    "Budget Buddy's database isn't encrypted yet, and this version can't encrypt it while "
    "database encryption is turned on. Turn off BUDGET_BUDDY_DATABASE_ENCRYPTION to keep using "
    "your data. Your data is safe and unchanged."
)
_SQLITE_HEADER = b"SQLite format 3\x00"
_NOT_A_DATABASE = "file is not a database"
_VERSION = re.compile(r"OpenSSL (\d+)\.(\d+)\.(\d+)")


def dbapi_module() -> Any:
    """SQLCipher's DB-API module (imported here so plain-SQLite runs never load it)."""
    import sqlcipher3.dbapi2

    return sqlcipher3.dbapi2


def provider_version(text: str) -> tuple[int, int, int] | None:
    """``(3, 6, 0)`` from ``OpenSSL 3.6.0 1 Oct 2025``, or None if the text isn't that."""
    found = _VERSION.search(text)
    return tuple(int(part) for part in found.groups()) if found else None  # type: ignore[return-value]


def refuse_plain_file(path: object) -> None:
    """Raise ``UnencryptedDatabaseError`` if ``path`` is an ordinary, unencrypted SQLite file.

    Without this a plain file would fail the key check and be reported as a wrong key, which
    sends people to the recovery phrase. Runs before the key is set (until roadmap 25l-3 moves
    existing databases; an empty new file is fine).
    """
    try:
        with open(Path(str(path)), "rb") as handle:
            start = handle.read(len(_SQLITE_HEADER))
    except OSError:
        return  # missing or unreadable: the connection reports it
    if start == _SQLITE_HEADER:
        raise UnencryptedDatabaseError(PLAIN_DATABASE_MESSAGE)


def is_encrypted_engine(engine: Engine) -> bool:
    """True when ``engine`` talks to SQLCipher."""
    return getattr(engine.dialect.dbapi, "__name__", "") == dbapi_module().__name__


def open_with_key(dbapi_connection, key: bytes) -> None:
    """Key a new SQLCipher connection and prove the key opens the file.

    Raises ``WrongKeyError`` (not a "busy" or "unreadable" error) when the key doesn't fit, and
    ``CipherProviderError`` when the bundled OpenSSL is older than ``MIN_PROVIDER_VERSION``.
    Any other failure, such as a locked file, is raised as it is.
    """
    if not isinstance(key, bytes) or len(key) != DATABASE_KEY_BYTES:
        raise WrongKeyError(WRONG_KEY_MESSAGE)
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(f"PRAGMA key = \"x'{key.hex()}'\"")  # raw cursor only; never logged
        cursor.execute("PRAGMA cipher_log_level = NONE")
        cursor.execute("PRAGMA cipher_provider_version")
        row = cursor.fetchone()
        version = provider_version(str(row[0])) if row else None
        if version is None or version < MIN_PROVIDER_VERSION:
            raise CipherProviderError(OLD_PROVIDER_MESSAGE)
        try:
            cursor.execute("SELECT count(*) FROM sqlite_master")
            cursor.fetchone()
        except dbapi_module().DatabaseError as exc:
            if _NOT_A_DATABASE not in str(exc):
                raise
            raise WrongKeyError(WRONG_KEY_MESSAGE) from None
    finally:
        cursor.close()


def key_on_connect(engine: Engine, key: bytes) -> None:
    """Make every new connection of ``engine`` open with ``key`` as its very first statement.

    This hooks ``do_connect`` (which opens the DB-API connection) rather than ``connect``,
    because SQLAlchemy's own set-up statements, such as ``PRAGMA read_uncommitted``, run before
    any ``connect`` listener.
    """

    def connect(dialect, _record, args, kwargs):
        if args:
            refuse_plain_file(args[0])
        connection = dialect.loaded_dbapi.connect(*args, **kwargs)
        try:
            open_with_key(connection, key)
        except BaseException:
            connection.close()
            raise
        return connection

    event.listen(engine, "do_connect", connect)
