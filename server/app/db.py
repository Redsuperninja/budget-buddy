"""Database connection: one SQLite file (``budget.db``) inside the data folder."""

import logging
import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.crypto import sqlcipher
from app.crypto.fields import FieldCipher, set_field_cipher

if TYPE_CHECKING:  # Alembic is slow to import, so it is only loaded when a migration runs
    pass

logger = logging.getLogger(__name__)

DB_FILENAME = "budget.db"
BUSY_TIMEOUT_MS = 5000
# Not bound to an engine here: each app passes its own engine (see ``get_session``), so tests
# with different data folders never share a database.
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


def database_path(data_dir: Path) -> Path:
    return data_dir / DB_FILENAME


def make_private_file(path: Path) -> None:
    """Create ``path`` if needed so only the current user can read it (macOS/Linux, issue #5)."""
    if not path.exists():
        os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
    if sys.platform != "win32":
        # os.open's mode is reduced by the umask and ignored if the file already exists.
        os.chmod(path, 0o600)


def _create_private_file(path: Path) -> None:
    make_private_file(path)
    if sys.platform != "win32":
        for suffix in ("-wal", "-shm"):  # SQLite's WAL sidecar files hold recent data too
            sidecar = path.with_name(path.name + suffix)
            if sidecar.exists():
                os.chmod(sidecar, 0o600)


def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    # Overwrite deleted data with zeros instead of leaving it in free pages.
    cursor.execute("PRAGMA secure_delete=ON")
    cursor.close()


def create_db_engine(
    data_dir: Path,
    field_cipher: FieldCipher | None = None,
    database_key: bytes | None = None,
) -> Engine:
    """Engine for ``<data_dir>/budget.db`` with foreign keys enforced and WAL journaling.

    ``field_cipher`` encrypts and decrypts the sensitive columns (ADR-0003). Without it, reading
    or writing those columns raises an error. ``database_key`` (the ``db-file`` subkey) opens the
    file with SQLCipher so the whole file is encrypted (ADR-0014); without it the file is plain
    SQLite. The key is set only on the raw connection, never in the URL or in SQL run through
    SQLAlchemy.
    """
    path = database_path(data_dir)
    _create_private_file(path)
    # URL.create, not an f-string: a "?" or "%" in the folder name must not be parsed as URL syntax.
    url = URL.create("sqlite", database=str(path))
    # hide_parameters: never put amounts or descriptions into error messages or logs.
    if database_key is None:
        engine = create_engine(url, hide_parameters=True)
    else:
        engine = create_engine(url, hide_parameters=True, module=sqlcipher.dbapi_module())
        sqlcipher.key_on_connect(engine, database_key)  # before any other SQL
    event.listen(engine, "connect", _set_sqlite_pragmas)
    if field_cipher is not None:
        set_field_cipher(engine, field_cipher)
    return engine


@contextmanager
def open_read_only(
    db_path: Path, database_key: bytes | None = None
) -> Iterator[sqlite3.Connection]:
    """A read-only connection to a database file (no engine, never creates it).

    With ``database_key`` the file is opened with SQLCipher and the key is proved first (ADR-0014):
    a wrong key, a plain file, a busy file or a damaged one each raise their own error, so a
    caller can't mistake any of them for "no data". Without it the file is plain SQLite.
    """
    if database_key is None:
        connection = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    else:
        connection = sqlcipher.connect(db_path, database_key, read_only=True)
    try:
        yield connection
    finally:
        connection.close()


def is_missing_table(exc: Exception) -> bool:
    """True for "no such table" from either SQLite or SQLCipher; every other error is real."""
    return str(exc).startswith("no such table")


def database_revision(db_path: Path, database_key: bytes | None = None) -> str | None:
    """The migration a database file is at, or None if it has no ``alembic_version`` table.

    Any other failure (wrong key, busy, damaged, not a database) is raised, not turned into
    "no revision".
    """
    with open_read_only(db_path, database_key) as connection:
        try:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        except Exception as exc:
            if not is_missing_table(exc):
                raise (sqlcipher.classify_error(exc) if database_key else exc) from None
            return None
    return row[0] if row else None


@contextmanager
def _exclusive_lock(lock_path: Path) -> Iterator[None]:
    """Hold an OS-level lock on ``lock_path`` so only one process/thread migrates at a time."""
    make_private_file(lock_path)
    with open(lock_path, "r+b") as lock_file:
        if sys.platform == "win32":
            import msvcrt

            while True:
                try:
                    # LK_LOCK retries for about 10 seconds before giving up; keep waiting.
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    continue
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def copy_database(engine: Engine, destination: Path, database_key: bytes | None = None) -> None:
    """Consistent copy of the database (including anything still in the WAL file).

    With ``database_key`` (the key the engine was made with) the copy is encrypted with the same
    key, so no plain copy of encrypted data is ever written.
    """
    make_private_file(destination)
    if database_key is None:
        target = sqlite3.connect(destination)
    else:
        target = sqlcipher.connect(destination, database_key)
    try:
        with engine.connect() as connection:
            connection.connection.driver_connection.backup(target)
    finally:
        target.close()


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: a database session for one request."""
    with SessionLocal(bind=request.app.state.engine) as session:
        yield session
