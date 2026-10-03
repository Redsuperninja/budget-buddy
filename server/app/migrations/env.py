"""Alembic environment. Uses the app's data folder and models, never a URL in alembic.ini."""

from logging.config import fileConfig

from alembic import context

from app.config import Settings
from app.crypto import FieldCipher, load_keys
from app.crypto.fields import alembic_compare_type
from app.db import create_db_engine
from app.main import ensure_data_dir
from app.models import Base

config = context.config
target_metadata = Base.metadata

# Only set up logging for the `alembic` command line; when the app runs migrations at
# startup it keeps its own logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """``alembic upgrade --sql``: print SQL instead of running it."""
    context.configure(
        url="sqlite://",
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        compare_type=alembic_compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:  # passed in by app.db.run_migrations
        _run(connection)
        return

    settings = Settings()
    ensure_data_dir(settings.data_dir)
    # Some migrations encrypt or decrypt columns, so they need the data folder's key.
    field_cipher = FieldCipher(load_keys(settings).db_fields)
    engine = create_db_engine(settings.data_dir, field_cipher=field_cipher)
    try:
        with engine.begin() as connection:
            _run(connection)
    finally:
        engine.dispose()


def _run(connection) -> None:
    # render_as_batch: SQLite can't ALTER most things, so Alembic rebuilds tables instead.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=alembic_compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
