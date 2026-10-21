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
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.crypto._fs import write_private_bytes
from app.crypto.fields import FieldCipher, set_field_cipher

if TYPE_CHECKING:  # Alembic is slow to import, so it is only loaded when a migration runs
    from alembic.config import Config

logger = logging.getLogger(__name__)

DB_FILENAME = "budget.db"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
BUSY_TIMEOUT_MS = 5000
# The newest migration. Lets start-up skip loading Alembic when the database is up to date.
# tests/test_migrations.py checks it against Alembic's real head: update it with a new migration.
HEAD_REVISION = "0028"
# Migration that encrypts sensitive columns (roadmap #4). Backups made before it hold plaintext.
FIRST_ENCRYPTED_REVISION = "0003"
# Migration that encrypts bank, employer, charity and shop names (#28). Database copies made
# before it (``budget.db.bak-<older revision>``) hold those names, and the old file pages and
# write-ahead log may too, as plain text.
NAMES_ENCRYPTED_REVISION = "0028"
# Written before that migration runs, removed once the leftover plain text has been cleaned out
# of the database file. While it exists, every start tries the clean-up again.
SCRUB_MARKER_FILENAME = "scrub-pending"

# Not bound to an engine here: each app passes its own engine (see ``get_session``), so tests
# with different data folders never share a database.
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


# A newer Budget Buddy already updated this database; this (older) copy can't read it.
NEWER_DATABASE_MESSAGE = (
    "Your data was last opened by a newer version of Budget Buddy, so this copy can't use it. "
    "Update this copy: in the launch folder, double-click Build desktop app, then Install desktop "
    "app. Your data is safe and unchanged."
)


class DatabaseUpgradeError(RuntimeError):
    """The database couldn't be brought up to date. The message is meant for the user."""


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


def create_db_engine(data_dir: Path, field_cipher: FieldCipher | None = None) -> Engine:
    """Engine for ``<data_dir>/budget.db`` with foreign keys enforced and WAL journaling.

    ``field_cipher`` encrypts and decrypts the sensitive columns (ADR-0003). Without it, reading
    or writing those columns raises an error.
    """
    path = database_path(data_dir)
    _create_private_file(path)
    # URL.create, not an f-string: a "?" or "%" in the folder name must not be parsed as URL syntax.
    url = URL.create("sqlite", database=str(path))
    # hide_parameters: never put amounts or descriptions into error messages or logs.
    engine = create_engine(url, hide_parameters=True)
    event.listen(engine, "connect", _set_sqlite_pragmas)
    if field_cipher is not None:
        set_field_cipher(engine, field_cipher)
    return engine


def alembic_config() -> "Config":
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def known_revisions() -> set[str]:
    """Every migration this version of Budget Buddy has, read from the script file names.

    Each script is named ``<revision>_<what it does>.py`` (a test checks this against Alembic).
    """
    return {p.name.split("_", 1)[0] for p in (MIGRATIONS_DIR / "versions").glob("[0-9]*_*.py")}


@contextmanager
def open_read_only(db_path: Path) -> Iterator[sqlite3.Connection]:
    """A plain read-only connection to a database file (no engine, never creates it)."""
    connection = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        yield connection
    finally:
        connection.close()


def database_revision(db_path: Path) -> str | None:
    """The migration a database file is at, or None if it has none."""
    with open_read_only(db_path) as connection:
        try:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        except sqlite3.DatabaseError:
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


def copy_database(engine: Engine, destination: Path) -> None:
    """Consistent copy of the database (including anything still in the WAL file)."""
    make_private_file(destination)
    target = sqlite3.connect(destination)
    try:
        with engine.connect() as connection:
            connection.connection.driver_connection.backup(target)
    finally:
        target.close()


def _upgrade(config: "Config", engine: Engine) -> None:
    from alembic import command

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def scrub_marker_path(db_path: Path) -> Path:
    return db_path.with_name(SCRUB_MARKER_FILENAME)


def _current_revision(connection) -> str | None:
    """The revision stored in ``alembic_version`` (None for a new database)."""
    try:
        row = connection.exec_driver_sql("SELECT version_num FROM alembic_version").first()
    except OperationalError:  # no such table yet
        return None
    return row[0] if row else None


def run_migrations(engine: Engine) -> None:
    """Bring the database up to date (``alembic upgrade head``). Safe to run on every start.

    Runs under a lock file so two copies starting at once can't both migrate. Before changing a
    database that already has data, a backup copy is saved next to it as ``budget.db.bak-<rev>``.

    When an existing database is first encrypted, a ``scrub-pending`` marker is written before
    the migration runs. As long as it exists, each start cleans leftover plain text out of the
    database file, and the marker is only removed once that has fully worked. So a power cut or
    a locked file during the clean-up just means it's retried next time.
    """
    db_path = Path(engine.url.database)
    marker = scrub_marker_path(db_path)

    with _exclusive_lock(db_path.with_name(db_path.name + ".lock")):
        with engine.connect() as connection:
            current = _current_revision(connection)
        if current is not None and current not in known_revisions():
            raise DatabaseUpgradeError(NEWER_DATABASE_MESSAGE)
        if current != HEAD_REVISION:
            _upgrade_with_backup(engine, db_path, alembic_config(), current)
        if marker.exists():
            _scrub_plaintext(engine, db_path)


def _upgrade_with_backup(
    engine: Engine, db_path: Path, config: "Config", current: str | None
) -> None:
    backup_path = None
    if current is not None:
        backup_path = db_path.with_name(f"{db_path.name}.bak-{current}")
        copy_database(engine, backup_path)
        if current.isdigit() and int(current) < int(NAMES_ENCRYPTED_REVISION):
            # Before the migration commits, so a crash right after it still leaves the marker.
            write_private_bytes(scrub_marker_path(db_path), b"")
    try:
        _upgrade(config, engine)
    except Exception as exc:
        message = "Budget Buddy couldn't update its database to work with this version."
        if backup_path is not None:
            message += f" A copy of your data from before the update is saved at {backup_path}."
        message += " Please close Budget Buddy and try again, or ask for help."
        raise DatabaseUpgradeError(message) from exc


def unencrypted_backups(db_path: Path) -> list[Path]:
    """Backup copies made before sensitive columns were encrypted (they hold plain text)."""
    found = []
    for backup in sorted(db_path.parent.glob(f"{db_path.name}.bak-*")):
        revision = backup.name.rsplit("-", 1)[-1]
        if revision.isdigit() and int(revision) < int(NAMES_ENCRYPTED_REVISION):
            found.append(backup)
    return found


def _vacuum_and_checkpoint(engine: Engine) -> bool:
    """Rewrite the database file and empty the write-ahead log. True only if both fully worked.

    ``wal_checkpoint(TRUNCATE)`` returns ``(busy, log pages, checkpointed pages)``. ``busy`` is
    1 when another connection was still reading, in which case the log (with old pages) was not
    emptied.
    """
    with engine.connect() as connection:
        connection.exec_driver_sql("VACUUM")
        busy, _log, _checkpointed = connection.exec_driver_sql(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).one()
    return busy == 0


def _scrub_plaintext(engine: Engine, db_path: Path) -> None:
    """Clean up plain text left behind when sensitive columns were first encrypted.

    Rewrites the database file (VACUUM) and empties the write-ahead log, so the old text isn't
    left in unused pages. The ``scrub-pending`` marker is removed only if that worked; otherwise
    it's tried again on the next start. Backup copies are never deleted automatically; the user
    is told about them instead.
    """
    try:
        done = _vacuum_and_checkpoint(engine)
    except Exception:
        logger.warning(
            "Budget Buddy couldn't finish clearing old unencrypted copies of your data out of "
            "its database file. It will try again the next time it starts.",
            exc_info=True,
        )
        return
    if not done:
        logger.warning(
            "Budget Buddy couldn't finish clearing old unencrypted copies of your data out of "
            "its database file, because something else had it open. It will try again the next "
            "time it starts."
        )
        return
    scrub_marker_path(db_path).unlink(missing_ok=True)
    backups = unencrypted_backups(db_path)
    if backups:
        logger.warning(
            "Budget Buddy now encrypts account numbers, notes, receipt file names, and bank, "
            "employer, charity and shop names. These older backup copies were made before that "
            "and are NOT encrypted: %s. Once you've "
            "checked Budget Buddy is working, delete them (or keep them somewhere safe).",
            ", ".join(str(b) for b in backups),
        )


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: a database session for one request."""
    with SessionLocal(bind=request.app.state.engine) as session:
        yield session
