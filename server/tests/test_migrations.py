"""Startup migrations: locking, backups, and plain-English failures."""

import sqlite3
import stat
import sys
import threading
import time

import pytest
from alembic import command
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


def _category_count(engine) -> int:
    with SessionLocal(bind=engine) as session:
        return session.scalar(select(func.count()).select_from(Category))


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
        assert _revision(engines[0]) == "0003"
        assert _category_count(engines[0]) == 18  # seed not duplicated
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
        assert _revision(engine) == "0003"
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
