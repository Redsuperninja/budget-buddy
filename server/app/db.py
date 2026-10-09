"""Database connection: one SQLite file (``budget.db``) inside the data folder."""

import logging
import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.crypto._fs import write_private_bytes
from app.crypto.fields import FieldCipher, set_field_cipher

logger = logging.getLogger(__name__)

DB_FILENAME = "budget.db"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
BUSY_TIMEOUT_MS = 5000
# Migration that encrypts sensitive columns (roadmap #4). Backups made before it hold plaintext.
FIRST_ENCRYPTED_REVISION = "0003"
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


def _make_private(path: Path) -> None:
    """Create ``path`` if needed so only the current user can read it (macOS/Linux, issue #5)."""
    if not path.exists():
        os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
    if sys.platform != "win32":
        # os.open's mode is reduced by the umask and ignored if the file already exists.
        os.chmod(path, 0o600)


def _create_private_file(path: Path) -> None:
    _make_private(path)
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


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


@contextmanager
def _exclusive_lock(lock_path: Path) -> Iterator[None]:
    """Hold an OS-level lock on ``lock_path`` so only one process/thread migrates at a time."""
    _make_private(lock_path)
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


def _backup(engine: Engine, destination: Path) -> None:
    """Consistent copy of the database (including anything still in the WAL file)."""
    _make_private(destination)
    target = sqlite3.connect(destination)
    try:
        with engine.connect() as connection:
            connection.connection.driver_connection.backup(target)
    finally:
        target.close()


def _upgrade(config: Config, engine: Engine) -> None:
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def scrub_marker_path(db_path: Path) -> Path:
    return db_path.with_name(SCRUB_MARKER_FILENAME)


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
    config = alembic_config()
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    known = {revision.revision for revision in scripts.walk_revisions()}

    with _exclusive_lock(db_path.with_name(db_path.name + ".lock")):
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        if current is not None and current not in known:
            raise DatabaseUpgradeError(NEWER_DATABASE_MESSAGE)
        if current != head:
            _upgrade_with_backup(engine, db_path, config, current)
        if marker.exists():
            _scrub_plaintext(engine, db_path)


def _upgrade_with_backup(
    engine: Engine, db_path: Path, config: Config, current: str | None
) -> None:
    backup_path = None
    if current is not None:
        backup_path = db_path.with_name(f"{db_path.name}.bak-{current}")
        _backup(engine, backup_path)
        if current.isdigit() and int(current) < int(FIRST_ENCRYPTED_REVISION):
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
        if revision.isdigit() and int(revision) < int(FIRST_ENCRYPTED_REVISION):
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
            "Budget Buddy now encrypts account numbers, notes, and receipt file names. These "
            "older backup copies were made before that and are NOT encrypted: %s. Once you've "
            "checked Budget Buddy is working, delete them (or keep them somewhere safe).",
            ", ".join(str(b) for b in backups),
        )


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: a database session for one request."""
    with SessionLocal(bind=request.app.state.engine) as session:
        yield session
