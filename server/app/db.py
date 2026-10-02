"""Database connection: one SQLite file (``budget.db``) inside the data folder."""

import os
import sys
from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DB_FILENAME = "budget.db"
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

# Not bound to an engine here: each app passes its own engine (see ``get_session``), so tests
# with different data folders never share a database.
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


def database_path(data_dir: Path) -> Path:
    return data_dir / DB_FILENAME


def _create_private_file(path: Path) -> None:
    """Create the DB file so only the current user can read it (macOS/Linux, see issue #5)."""
    if not path.exists():
        os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
    if sys.platform != "win32":
        # os.open's mode is reduced by the umask and ignored if the file already exists.
        os.chmod(path, 0o600)


def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def create_db_engine(data_dir: Path) -> Engine:
    """Engine for ``<data_dir>/budget.db`` with foreign keys enforced and WAL journaling."""
    path = database_path(data_dir)
    _create_private_file(path)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def run_migrations(engine: Engine) -> None:
    """Bring the database up to date (``alembic upgrade head``). Safe to run on every start."""
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: a database session for one request."""
    with SessionLocal(bind=request.app.state.engine) as session:
        yield session
