"""First-start setup progress (roadmap 25e, ADR-0015): migration 0029 and /api/local/setup."""

import pytest
from alembic import command
from crypto_helpers import raw_rows
from sqlalchemy import text

from app import cli
from app.crypto import MemoryKeyStore
from app.crypto import keystore as keystore_module
from app.db import alembic_config, create_db_engine

SETUP = "/api/local/setup"
EMPTY = {"finished_at": None, "phrase_saved_at": None, "last_backup_at": None}


def _migrate(engine, target, direction="upgrade"):
    config = alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        getattr(command, direction)(config, target)


def _tables(engine) -> set[str]:
    with engine.connect() as conn:
        return {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master"))}


@pytest.mark.real_migrations
def test_migration_0029_adds_and_removes_the_table(tmp_path):
    engine = create_db_engine(tmp_path)
    try:
        _migrate(engine, "0028")
        assert "setup_progress" not in _tables(engine)
        _migrate(engine, "0029")
        assert "setup_progress" in _tables(engine)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO setup_progress (id) VALUES (1)"))
        with pytest.raises(Exception, match="(?i)constraint"), engine.begin() as conn:
            conn.execute(text("INSERT INTO setup_progress (id) VALUES (2)"))
        _migrate(engine, "0028", "downgrade")
        assert "setup_progress" not in _tables(engine)
    finally:
        engine.dispose()


def test_a_fresh_database_has_nothing_done(client):
    assert client.get(SETUP).json() == EMPTY


def test_put_round_trip(client):
    saved = client.put(SETUP, json={"phrase_saved": True}).json()
    assert saved["phrase_saved_at"] and saved["finished_at"] is None
    assert client.get(SETUP).json() == saved

    both = client.put(SETUP, json={"finished": True}).json()
    assert both["finished_at"] and both["phrase_saved_at"] == saved["phrase_saved_at"]

    again = client.put(SETUP, json={"phrase_saved": True}).json()  # stamped once
    assert again["phrase_saved_at"] == saved["phrase_saved_at"]

    cleared = client.put(SETUP, json={"finished": False}).json()
    assert cleared["finished_at"] is None and cleared["phrase_saved_at"]
    assert client.put(SETUP, json={}).json() == cleared


@pytest.mark.parametrize(
    "body",
    [
        {"nope": True},
        {"last_backup_at": "2026-01-01T00:00:00"},
        {"finished_at": "2026-01-01T00:00:00"},
        {"finished": "maybe"},
        {"finished": 2},
    ],
)
def test_put_refuses_unknown_fields_and_client_set_times(client, body):
    assert client.put(SETUP, json=body).status_code == 422
    assert client.get(SETUP).json() == EMPTY


def test_put_needs_the_csrf_origin(make_client):
    client = make_client(headers={"Origin": "http://evil.example"})
    assert client.put(SETUP, json={"finished": True}).status_code == 403


@pytest.mark.parametrize("method", ["get", "put"])
def test_other_computers_are_refused(make_client, method):
    lan = make_client("192.168.1.20")
    response = lan.request(method, SETUP, json={})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_this_computer"


@pytest.fixture
def store(monkeypatch):
    fresh = MemoryKeyStore()
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", fresh)
    return fresh


@pytest.mark.real_migrations
def test_the_dashboard_backup_sets_last_backup_at(client, store):
    assert client.get(SETUP).json()["last_backup_at"] is None
    assert client.get("/api/local/backup/file").status_code == 200
    stamped = client.get(SETUP).json()
    assert stamped["last_backup_at"] and stamped["finished_at"] is None


@pytest.mark.real_migrations
def test_the_command_line_backup_sets_last_backup_at(make_client, store, tmp_path):
    client = make_client()
    client.app.state.engine.dispose()
    out = tmp_path / "out"
    out.mkdir()
    messages: list[str] = []
    assert cli.main(["backup", "make", "--to", str(out)], output=messages.append) == 0
    assert raw_rows_backup_stamp(client) is not None


def raw_rows_backup_stamp(client):
    client = client.app.state.engine
    with client.connect() as conn:
        return conn.execute(text("SELECT last_backup_at FROM setup_progress")).scalar()


@pytest.mark.real_migrations
def test_a_failed_backup_leaves_it_unset(make_client, store, tmp_path):
    client = make_client()
    client.app.state.engine.dispose()
    code = cli.main(["backup", "make", "--to", str(tmp_path / "missing")], output=lambda _m: None)
    assert code == 1
    assert client.get(SETUP).json()["last_backup_at"] is None
    assert raw_rows(client.app.state.settings.data_dir, "SELECT * FROM setup_progress") == []
