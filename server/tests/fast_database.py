"""Build the migrated database once per test session and hand each new app a copy.

Running all the migrations costs about 0.4 s, and nearly every test makes an app. The fresh
database holds no encrypted values (only the starter categories), so the copy doesn't depend on
any key. Only a brand-new, empty database file is replaced; anything that already has tables goes
through the real ``run_migrations``. Tests of the migrations themselves opt out with
``@pytest.mark.real_migrations``.
"""

import sqlite3
from pathlib import Path

from sqlalchemy import Engine

from app.db import create_db_engine, run_migrations


def build_template(folder: Path) -> Path:
    """Migrate a new database in ``folder`` the real way and return its path."""
    folder.mkdir(parents=True, exist_ok=True)
    engine = create_db_engine(folder)
    try:
        run_migrations(engine)
        with engine.connect() as connection:  # fold the WAL into the main file
            connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        engine.dispose()
    return folder / "budget.db"


def migrations_from_template(template: Path):
    """A stand-in for ``app.main.run_migrations`` that starts empty databases from the template."""

    def run(engine: Engine) -> None:
        with engine.connect() as connection:
            empty = connection.exec_driver_sql("SELECT count(*) FROM sqlite_master").scalar() == 0
            if empty:
                source = sqlite3.connect(template)
                try:
                    source.backup(connection.connection.driver_connection)
                finally:
                    source.close()
                return  # at head already; reading the migration files again would cost 0.1 s
        run_migrations(engine)

    return run
