"""Backups and restores with whole-database encryption on (ADR-0014; roadmap 25l-4)."""

import pytest
from sqlalchemy.orm import Session

from app.backup.restore import (
    BackupKey,
    RestoreError,
    carry_over_removals,
    check_backup,
)
from app.crypto import MemoryKeyStore
from app.crypto import keystore as keystore_module
from app.crypto.keys import generate_master_key
from app.models.devices import Device
from tests.backup.test_backup_restore import account_names, run

pytestmark = pytest.mark.real_migrations
HEADER = b"SQLite format 3\x00"


@pytest.fixture(autouse=True)
def encryption_on(monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_DATABASE_ENCRYPTION", "1")
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", MemoryKeyStore())


@pytest.fixture
def saved(data_dir, make_client, tmp_path):
    client = make_client()
    client.post("/api/local/accounts", json={"name": "Everyday", "kind": "checking"})
    client.app.state.engine.dispose()
    out = tmp_path / "out"
    out.mkdir()
    code, text = run(["backup", "make", "--to", str(out)])
    assert code == 0, text
    [backup] = out.glob("*.bbbackup")
    return backup


def test_a_backup_of_an_encrypted_database_restores(saved, data_dir, make_client):
    client = make_client()
    client.post("/api/local/accounts", json={"name": "Added later", "kind": "savings"})
    client.app.state.engine.dispose()
    code, text = run(["backup", "restore", str(saved)], ["RESTORE"])
    assert code == 0, text
    client = make_client()
    assert account_names(client) == ["Everyday"]
    client.app.state.engine.dispose()
    assert not (data_dir / "budget.db").read_bytes().startswith(HEADER)
    assert not list(data_dir.glob(".backup-*")) and not list(data_dir.glob(".restore-*"))


def _master(data_dir):
    return keystore_module._MEMORY_STORE.get(keystore_module.key_name_for(data_dir))


def test_the_staged_copy_of_the_database_is_never_plain(saved, data_dir):
    import shutil

    staging, _manifest = check_backup(
        saved, data_dir, BackupKey.from_master(_master(data_dir), True)
    )
    try:
        data = (staging / "budget.db").read_bytes()
        assert not data.startswith(HEADER) and b"CREATE TABLE" not in data
        assert b"Everyday" not in data
    finally:
        shutil.rmtree(staging)


def test_an_encrypted_backup_is_refused_when_the_setting_is_off(saved, data_dir, monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_DATABASE_ENCRYPTION", "0")
    with pytest.raises(RestoreError, match="database encryption is turned off"):
        check_backup(saved, data_dir, BackupKey.from_master(_master(data_dir), False))
    assert not list(data_dir.glob(".restore-*"))


def test_a_phone_removed_after_the_backup_stays_removed(data_dir, make_client, tmp_path):
    client = make_client()
    with Session(client.app.state.engine) as session:
        session.add(Device(name="Phone", token_hash="a" * 64))
        session.commit()
    client.app.state.engine.dispose()
    out = tmp_path / "out"
    out.mkdir()
    assert run(["backup", "make", "--to", str(out)])[0] == 0
    [backup] = out.glob("*.bbbackup")
    client = make_client()
    with Session(client.app.state.engine) as session:
        session.query(Device).one().revoked = True
        session.commit()
    client.app.state.engine.dispose()
    code, text = run(["backup", "restore", str(backup)], ["RESTORE"])
    assert code == 0, text
    client = make_client()
    with Session(client.app.state.engine) as session:
        assert session.query(Device).one().revoked
    client.app.state.engine.dispose()


@pytest.mark.parametrize("which", ["this computer's", "the backup's"])
def test_a_wrong_key_for_either_database_stops_the_carry_over(tmp_path, which):
    from app.crypto import sqlcipher

    key, other = generate_master_key(), generate_master_key()
    old, new = tmp_path / "old.db", tmp_path / "new.db"
    for path in (old, new):
        connection = sqlcipher.connect(path, key[:32])
        connection.execute(
            "CREATE TABLE devices (token_hash TEXT, revoked INT, revoked_at INT, sync_key TEXT)"
        )
        connection.commit()
        connection.close()
    old_key, new_key = (
        (other[:32], key[:32]) if which == "this computer's" else (key[:32], other[:32])
    )
    with pytest.raises(RestoreError, match="stopped before replacing anything"):
        carry_over_removals(old, new, old_key, new_key)


def test_a_plain_backup_is_refused_under_the_setting_until_it_can_be_converted(
    data_dir, tmp_path, monkeypatch, make_client
):
    monkeypatch.setenv("BUDGET_BUDDY_DATABASE_ENCRYPTION", "0")
    client = make_client()
    client.app.state.engine.dispose()
    out = tmp_path / "plain"
    out.mkdir()
    assert run(["backup", "make", "--to", str(out)])[0] == 0
    [backup] = out.glob("*.bbbackup")
    with pytest.raises(RestoreError, match="before database encryption existed"):
        check_backup(backup, data_dir, BackupKey.from_master(_master(data_dir), True))
