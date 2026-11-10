"""Tax preferences (roadmap 25j): migration 0030, /api/local/tax-preferences, who may use it, and
that backups and restores carry it like other data. Fake data only."""

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import cli
from app.crypto import MemoryKeyStore
from app.crypto import keystore as keystore_module
from app.db import create_db_engine
from app.db_migrate import alembic_config
from app.tax_data import FILING_STATUSES

PREFS = "/api/local/tax-preferences"
NOT_SET = {"filing_status": None}
LAN_BASE = "http://192.168.1.20:8765"


def _migrate(engine, target, direction="upgrade"):
    config = alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        getattr(command, direction)(config, target)


def _tables(engine) -> set[str]:
    with engine.connect() as conn:
        return {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master"))}


def _insert(engine, sql: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(sql))


@pytest.mark.real_migrations
def test_migration_0030_adds_and_removes_the_table(tmp_path):
    engine = create_db_engine(tmp_path)
    try:
        _migrate(engine, "0029")
        assert "tax_preferences" not in _tables(engine)
        _migrate(engine, "0030")
        assert "tax_preferences" in _tables(engine)
        _insert(engine, "INSERT INTO tax_preferences (id, filing_status) VALUES (1, NULL)")
        _insert(engine, "UPDATE tax_preferences SET filing_status = 'head_of_household'")
        for bad in (
            "INSERT INTO tax_preferences (id) VALUES (2)",  # one row only
            "UPDATE tax_preferences SET filing_status = 'qualifying_surviving_spouse'",
            "UPDATE tax_preferences SET filing_status = 'Single'",
        ):
            with pytest.raises(Exception, match="(?i)constraint"):
                _insert(engine, bad)
        _migrate(engine, "0029", "downgrade")
        assert "tax_preferences" not in _tables(engine)
        _migrate(engine, "0030")  # and back up again from there
        assert "tax_preferences" in _tables(engine)
    finally:
        engine.dispose()


def test_a_fresh_database_has_no_filing_status(client):
    assert client.get(PREFS).json() == NOT_SET


@pytest.mark.parametrize("status", FILING_STATUSES)
def test_put_round_trip(client, status):
    assert client.put(PREFS, json={"filing_status": status}).json() == {"filing_status": status}
    assert client.get(PREFS).json() == {"filing_status": status}


def test_null_goes_back_to_showing_all(client):
    client.put(PREFS, json={"filing_status": "single"})
    assert client.put(PREFS, json={"filing_status": None}).json() == NOT_SET
    assert client.get(PREFS).json() == NOT_SET


@pytest.mark.parametrize(
    "body",
    [
        {"filing_status": "qualifying_surviving_spouse"},  # not in the tax-year data files
        {"filing_status": "Single"},
        {"filing_status": ""},
        {"filing_status": 1},
        {"filing_status": "single", "extra": True},
    ],
)
def test_put_refuses_unknown_statuses_and_fields(client, body):
    client.put(PREFS, json={"filing_status": "married_filing_jointly"})
    assert client.put(PREFS, json=body).status_code == 422
    assert client.get(PREFS).json() == {"filing_status": "married_filing_jointly"}


def test_put_needs_the_csrf_origin(make_client):
    client = make_client(headers={"Origin": "http://evil.example"})
    assert client.put(PREFS, json={"filing_status": "single"}).status_code == 403


def test_put_needs_the_csrf_token(client):
    wrong = {"X-CSRF-Token": "wrong"}
    assert client.put(PREFS, json={"filing_status": "single"}, headers=wrong).status_code == 403
    assert client.get(PREFS).json() == NOT_SET


@pytest.mark.parametrize("method", ["get", "put"])
def test_a_computer_that_hasnt_joined_is_refused(make_client, method):
    response = make_client("192.168.1.20").request(method, PREFS, json=NOT_SET)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_this_computer"


def test_a_joined_computer_may_read_and_choose_it(client):
    laptop = TestClient(
        client.app, client=("192.168.1.50", 50000), base_url=LAN_BASE, headers={"Origin": LAN_BASE}
    )
    code = client.post("/api/local/remote-computers/join-code").json()["code"]
    assert laptop.post("/api/remote/join", json={"code": code, "name": "Fake laptop"}).is_success
    laptop.headers["X-CSRF-Token"] = client.app.state.csrf_token
    assert laptop.put(PREFS, json={"filing_status": "single"}).status_code == 200
    assert client.get(PREFS).json() == {"filing_status": "single"}


@pytest.fixture
def store(monkeypatch):
    fresh = MemoryKeyStore()
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", fresh)
    return fresh


@pytest.mark.real_migrations
def test_a_restore_brings_back_the_backups_filing_status(store, make_client, tmp_path):
    client = make_client()
    client.put(PREFS, json={"filing_status": "married_filing_jointly"})
    client.app.state.engine.dispose()
    out = tmp_path / "out"
    out.mkdir()
    assert cli.main(["backup", "make", "--to", str(out)], output=lambda _m: None) == 0
    [backup] = out.glob("*.bbbackup")

    client = make_client()
    client.put(PREFS, json={"filing_status": "single"})  # changed after the backup
    client.app.state.engine.dispose()
    code = cli.main(
        ["backup", "restore", str(backup)], output=lambda _m: None, ask=lambda _p: "RESTORE"
    )
    assert code == 0
    client = make_client()
    assert client.get(PREFS).json() == {"filing_status": "married_filing_jointly"}
    client.app.state.engine.dispose()


@pytest.mark.real_migrations
def test_a_new_computer_with_only_a_filing_status_can_restore_another_keys_backup(
    store, data_dir, tmp_path, monkeypatch, make_client
):
    from app.crypto import key_name_for, master_key_to_phrase

    client = make_client()
    client.put(PREFS, json={"filing_status": "head_of_household"})
    backup = client.get("/api/local/backup/file").content
    phrase = master_key_to_phrase(store.get(key_name_for(data_dir)))
    client.app.state.engine.dispose()

    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", MemoryKeyStore())
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(tmp_path / "other"))
    new = make_client()
    assert new.put(PREFS, json={"filing_status": "single"}).status_code == 200  # not encrypted
    response = new.post(
        "/api/local/backup/restore", content=backup, headers={"X-Recovery-Phrase": phrase}
    )
    assert response.status_code == 200, response.text
    new.app.state.engine.dispose()
    restarted = make_client()  # the restore finishes at the next start
    assert restarted.get(PREFS).json() == {"filing_status": "head_of_household"}
    restarted.app.state.engine.dispose()
