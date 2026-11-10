"""Migration 0032 (transaction splits): up, down, and nothing else changes."""

import pytest
from alembic import command
from sqlalchemy import inspect, text

from app.db import create_db_engine
from app.db_migrate import alembic_config

pytestmark = pytest.mark.real_migrations


def _migrate(engine, direction, revision):
    with engine.begin() as connection:
        config = alembic_config()
        config.attributes["connection"] = connection
        getattr(command, direction)(config, revision)


def test_0032_adds_the_table_and_downgrade_removes_it(tmp_path):
    engine = create_db_engine(tmp_path)
    try:
        _migrate(engine, "upgrade", "0031")
        assert "transaction_splits" not in inspect(engine).get_table_names()
        _migrate(engine, "upgrade", "0032")
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("transaction_splits")}
        assert columns == {
            "id",
            "transaction_id",
            "category_id",
            "amount_cents",
            "note",
            "created_at",
            "updated_at",
        }
        fks = {
            (fk["referred_table"], fk["options"].get("ondelete"))
            for fk in inspector.get_foreign_keys("transaction_splits")
        }
        assert fks == {("transactions", "CASCADE"), ("categories", None)}
        _migrate(engine, "downgrade", "0031")
        assert "transaction_splits" not in inspect(engine).get_table_names()
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM transactions")).scalar() == 0
    finally:
        engine.dispose()
