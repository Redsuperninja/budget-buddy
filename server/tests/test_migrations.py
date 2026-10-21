"""Startup migrations: locking, backups, and plain-English failures."""

import io
import re
import sqlite3
import stat
import sys
import threading
import time

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text

from app import db
from app.db import (
    DatabaseUpgradeError,
    SessionLocal,
    alembic_config,
    create_db_engine,
    database_path,
    run_migrations,
)
from app.models import Category

pytestmark = pytest.mark.real_migrations


def _category_count(engine) -> int:
    with SessionLocal(bind=engine) as session:
        return session.scalar(select(func.count()).select_from(Category))


# The newest migration. Not hard-coded, so adding a migration doesn't break these tests.
HEAD = ScriptDirectory.from_config(alembic_config()).get_current_head()


def _revision(engine) -> str:
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def test_concurrent_startups_migrate_once(tmp_path, monkeypatch):
    real_upgrade = db._upgrade
    calls = []

    def slow_upgrade(config, engine):
        calls.append(threading.get_ident())
        time.sleep(0.3)  # make sure the other thread is waiting on the lock meanwhile
        real_upgrade(config, engine)

    monkeypatch.setattr(db, "_upgrade", slow_upgrade)
    engines = [create_db_engine(tmp_path) for _ in range(2)]
    barrier = threading.Barrier(2)
    errors = []

    def start(engine):
        try:
            barrier.wait()
            run_migrations(engine)
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=start, args=(e,)) for e in engines]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    try:
        assert errors == []
        assert len(calls) == 1
        assert _revision(engines[0]) == HEAD
        assert _category_count(engines[0]) == 19  # seed not duplicated
    finally:
        for engine in engines:
            engine.dispose()


def test_fresh_database_is_not_backed_up(tmp_path):
    engine = create_db_engine(tmp_path)
    run_migrations(engine)
    engine.dispose()
    assert not list(tmp_path.glob("budget.db.bak-*"))


def test_backup_made_before_upgrading_existing_database(tmp_path):
    engine = create_db_engine(tmp_path)
    try:
        config = alembic_config()
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0001")
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO accounts (name, kind) VALUES ('Mine', 'checking')"))

        run_migrations(engine)

        backup = tmp_path / "budget.db.bak-0001"
        assert backup.is_file()
        with sqlite3.connect(backup) as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("0001",)
            assert conn.execute("SELECT name FROM accounts").fetchall() == [("Mine",)]
            assert conn.execute("SELECT count(*) FROM categories").fetchone() == (0,)
        if sys.platform != "win32":
            assert stat.S_IMODE(backup.stat().st_mode) == 0o600
        assert _revision(engine) == HEAD
    finally:
        engine.dispose()


def test_failed_upgrade_gives_plain_english_error(tmp_path, monkeypatch):
    engine = create_db_engine(tmp_path)
    try:
        config = alembic_config()
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0001")

        def broken_upgrade(config, engine):
            raise RuntimeError("boom")

        monkeypatch.setattr(db, "_upgrade", broken_upgrade)
        with pytest.raises(DatabaseUpgradeError, match="couldn't update its database") as info:
            run_migrations(engine)
        assert str(database_path(tmp_path)) + ".bak-0001" in str(info.value)
        assert isinstance(info.value.__cause__, RuntimeError)
    finally:
        engine.dispose()


def test_migrations_have_one_head_and_no_duplicate_revision_ids():

    from alembic.script import ScriptDirectory

    assert len(ScriptDirectory.from_config(alembic_config()).get_heads()) == 1
    versions = db.MIGRATIONS_DIR / "versions"
    matches = [
        re.search(r'^revision(?::\s*str)?\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8"), re.M)
        for p in sorted(versions.glob("*.py"))
        if p.name != "__init__.py"
    ]
    found = [m.group(1) for m in matches if m]
    assert len(found) == len(matches)  # every file declares a revision
    assert len(found) == len(set(found)), f"duplicate revision ids: {found}"


def test_migration_0007_works_in_offline_sql_mode():
    """``alembic upgrade --sql`` prints the script instead of running it."""
    config = alembic_config()
    config.output_buffer = io.StringIO()
    command.upgrade(config, "0006:0007", sql=True)
    script = config.output_buffer.getvalue()
    assert "INSERT INTO stock_sale_orders" in script
    assert "UPDATE stock_sales SET order_id = id" in script


def test_migration_0007_turns_existing_stock_sales_into_orders(tmp_path):
    engine = create_db_engine(tmp_path)
    config = alembic_config()

    def migrate(direction, target):
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            getattr(command, direction)(config, target)

    try:
        migrate("upgrade", "0006")
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO accounts (id, name, kind) VALUES (1, 'B', 'brokerage')"))
            conn.execute(
                text(
                    "INSERT INTO stock_lots (id, account_id, symbol, shares_micro, acquired_on, "
                    "cost_basis_cents) VALUES (1, 1, 'FAKE', 3000000, '2025-01-02', 3000)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO stock_sales (lot_id, sold_on, shares_micro, proceeds_cents) "
                    "VALUES (1, '2026-02-01', 1000000, 1500), (1, '2026-03-01', 2000000, 2500)"
                )
            )

        migrate("upgrade", "0007")
        with engine.connect() as conn:
            orders = conn.execute(
                text(
                    "SELECT id, account_id, symbol, sold_on, shares_micro, proceeds_cents "
                    "FROM stock_sale_orders ORDER BY id"
                )
            ).all()
            pieces = conn.execute(
                text("SELECT order_id, lot_id, shares_micro FROM stock_sales ORDER BY id")
            ).all()
        assert [tuple(o)[1:] for o in orders] == [
            (1, "FAKE", "2026-02-01", 1_000_000, 1500),
            (1, "FAKE", "2026-03-01", 2_000_000, 2500),
        ]
        assert [tuple(p) for p in pieces] == [
            (orders[0].id, 1, 1_000_000),
            (orders[1].id, 1, 2_000_000),
        ]
        assert _revision(engine) == "0007"

        migrate("downgrade", "0006")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM stock_sales")).scalar() == 2
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(stock_sales)"))]
            assert "order_id" not in columns
    finally:
        engine.dispose()


def test_a_newer_database_gets_a_clear_message(tmp_path):
    engine = create_db_engine(tmp_path)
    try:
        run_migrations(engine)
        with engine.begin() as conn:
            conn.execute(text("UPDATE alembic_version SET version_num = '9999'"))
        with pytest.raises(DatabaseUpgradeError, match="newer version of Budget Buddy"):
            run_migrations(engine)
        assert _revision(engine) == "9999"  # nothing was changed
    finally:
        engine.dispose()


def test_migration_0018_keeps_your_own_other_expenses_category(tmp_path):
    engine = create_db_engine(tmp_path)
    config = alembic_config()

    def migrate(direction, target):
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            getattr(command, direction)(config, target)

    def other_expenses():
        with engine.connect() as conn:
            sql = "SELECT name, \"group\" FROM categories WHERE lower(name) = 'other expenses'"
            return [tuple(row) for row in conn.execute(text(sql))]

    try:
        migrate("upgrade", "0017")
        with engine.begin() as conn:
            conn.execute(
                text(
                    'INSERT INTO categories (name, "group", budget_cents) '
                    "VALUES ('other expenses', 'needs', 5000)"
                )
            )
        migrate("upgrade", "0018")
        assert other_expenses() == [("other expenses", "needs")]  # yours, not a second one

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM categories WHERE name = 'other expenses'"))
        migrate("downgrade", "0017")
        migrate("upgrade", "0018")
        assert other_expenses() == [("Other Expenses", "wants")]

        with engine.begin() as conn:  # now used: a downgrade keeps it
            conn.execute(text("INSERT INTO accounts (id, name, kind) VALUES (1, 'C', 'checking')"))
            conn.execute(
                text(
                    "INSERT INTO transactions (account_id, date, amount_cents, description, "
                    "category_id, source, kind) SELECT 1, '2026-01-02', -500, 'Fake', id, "
                    "'manual', 'normal' FROM categories WHERE name = 'Other Expenses'"
                )
            )
        migrate("downgrade", "0017")
        assert other_expenses() == [("Other Expenses", "wants")]
    finally:
        engine.dispose()
