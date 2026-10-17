"""``python -m app backup make|restore``: a backup brings everything back, and a bad one changes
nothing (ADR-0012)."""

import io
import json
import os
import tarfile

import pytest
from fastapi.testclient import TestClient

from app import cli, instance_proof
from app.backup.archive import BackupContentsError, extract_backup
from app.crypto import MemoryKeyStore, key_name_for, master_key_to_phrase
from app.crypto import keystore as keystore_module
from app.crypto.keys import PURPOSE_BACKUP, derive_key, fingerprint
from app.crypto.stream import EncryptingWriter, read_header
from app.main import create_app


def run(argv, answers=()):
    output: list[str] = []
    answers = iter(answers)
    code = cli.main(
        argv,
        output=output.append,
        ask=lambda _p: next(answers),
        ask_secret=lambda _p: next(answers),
    )
    return code, "\n".join(output)


@pytest.fixture
def store(monkeypatch):
    fresh = MemoryKeyStore()
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", fresh)
    return fresh


def account_names(client) -> list[str]:
    return sorted(a["name"] for a in client.get("/api/local/accounts").json())


@pytest.fixture
def saved(data_dir, store, make_client, tmp_path):
    """A data folder with one account and one receipt file, backed up into ``tmp_path/out``."""
    client = make_client()
    assert (
        client.post(
            "/api/local/accounts", json={"name": "Everyday", "kind": "checking"}
        ).status_code
        == 201
    )
    receipt_id = client.app.state.receipt_store.save(b"photo bytes")
    client.app.state.engine.dispose()
    out = tmp_path / "out"
    out.mkdir()
    code, text = run(["backup", "make", "--to", str(out)])
    assert code == 0, text
    [backup] = out.glob("*.bbbackup")
    return backup, receipt_id


def test_restore_brings_back_what_was_backed_up(saved, data_dir, make_client):
    backup, receipt_id = saved
    client = make_client()
    client.post("/api/local/accounts", json={"name": "Added later", "kind": "savings"})
    client.app.state.engine.dispose()

    code, text = run(["backup", "restore", str(backup)], ["RESTORE"])
    assert code == 0, text
    client = make_client()
    assert account_names(client) == ["Everyday"]
    assert client.app.state.receipt_store.load(receipt_id) == b"photo bytes"
    client.app.state.engine.dispose()
    [before] = data_dir.glob("before-restore-*")
    assert (before / "budget.db").is_file()  # the replaced data is kept, not deleted
    assert not list(data_dir.glob(".restore-*"))


def test_cancelling_changes_nothing(saved, data_dir, make_client):
    backup, _ = saved
    code, text = run(["backup", "restore", str(backup)], [""])
    assert code == 1 and "Cancelled" in text
    assert not list(data_dir.glob("before-restore-*")) and not list(data_dir.glob(".restore-*"))


def test_never_while_budget_buddy_runs(saved, data_dir):
    backup, _ = saved
    instance_proof.write(data_dir, 8765, instance_proof.new_key())  # this process: alive
    code, text = run(["backup", "restore", str(backup)], ["RESTORE"])
    assert code == 1 and "Close it first" in text


def test_a_damaged_backup_changes_nothing(saved, data_dir):
    backup, _ = saved
    blob = bytearray(backup.read_bytes())
    blob[-100] ^= 1
    backup.write_bytes(bytes(blob))
    code, text = run(["backup", "restore", str(backup)], ["RESTORE"])
    assert code == 1 and "changed or damaged" in text and "Nothing was changed" in text
    assert not list(data_dir.glob(".restore-*")) and not list(data_dir.glob("before-restore-*"))


def test_a_new_computer_needs_the_recovery_phrase(
    saved, store, data_dir, tmp_path, monkeypatch, make_client
):
    backup, receipt_id = saved
    phrase = master_key_to_phrase(store.get(key_name_for(data_dir)))
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", MemoryKeyStore())  # a new computer
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(tmp_path / "new-computer"))

    code, text = run(["backup", "restore", str(backup)], [master_key_to_phrase(os.urandom(32))])
    assert code == 1 and "isn't the one this backup was made with" in text

    code, text = run(["backup", "restore", str(backup)], [phrase])
    assert code == 0, text
    client = make_client()
    assert account_names(client) == ["Everyday"]
    assert client.app.state.receipt_store.load(receipt_id) == b"photo bytes"
    client.app.state.engine.dispose()


def test_another_keys_backup_never_replaces_data_of_its_own(
    saved, store, data_dir, tmp_path, monkeypatch, make_client
):
    backup, _ = saved
    phrase = master_key_to_phrase(store.get(key_name_for(data_dir)))
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", MemoryKeyStore())
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(tmp_path / "other"))
    client = make_client()  # a folder with its own key and its own data
    client.post("/api/local/accounts", json={"name": "Mine", "kind": "checking"})
    client.app.state.engine.dispose()

    code, text = run(["backup", "restore", str(backup)], [phrase])
    assert code == 1 and "already holds data under a different key" in text


def test_a_backup_holds_no_keys(saved):
    backup, _ = saved
    assert b"key-fingerprint" not in backup.read_bytes()  # names are encrypted too


def test_unexpected_names_are_refused(tmp_path):
    """A backup that decrypts but holds anything else (like a path out of the folder) is refused."""
    key = bytes(32)
    out = io.BytesIO()
    writer = EncryptingWriter(out, derive_key(key, PURPOSE_BACKUP), fingerprint(key))
    with tarfile.open(fileobj=writer, mode="w|") as tar:
        for name, data in (
            ("manifest.json", json.dumps({"format": 1}).encode()),
            ("../evil.txt", b"x"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    writer.close()
    source = io.BytesIO(out.getvalue())
    _fp, salt, header = read_header(source)
    staging = tmp_path / "staging"
    staging.mkdir()
    with pytest.raises(BackupContentsError):
        extract_backup(source, derive_key(key, PURPOSE_BACKUP), salt, header, staging)
    assert not (tmp_path / "evil.txt").exists()


def test_a_phone_removed_after_the_backup_stays_removed(data_dir, store, make_client, tmp_path):
    from sqlalchemy.orm import Session

    from app.models.devices import Device

    client = make_client()
    with Session(client.app.state.engine) as session:
        session.add(Device(name="Phone", token_hash="a" * 64))
        session.commit()
    client.app.state.engine.dispose()
    out = tmp_path / "out"
    out.mkdir()
    assert run(["backup", "make", "--to", str(out)])[0] == 0
    [backup] = out.glob("*.bbbackup")

    client = make_client()  # the phone is lost, and removed
    with Session(client.app.state.engine) as session:
        phone = session.query(Device).one()
        phone.revoked = True
        session.commit()
    client.app.state.engine.dispose()

    code, text = run(["backup", "restore", str(backup)], ["RESTORE"])
    assert code == 0, text
    client = make_client()
    with Session(client.app.state.engine) as session:
        assert session.query(Device).one().revoked
    client.app.state.engine.dispose()


def test_never_while_a_home_base_holds_the_folder(saved, data_dir):
    from app import run_lock

    backup, _ = saved
    lock = run_lock.try_lock(data_dir)  # as a running Home Base does
    try:
        code, text = run(["backup", "restore", str(backup)], ["RESTORE"])
    finally:
        run_lock.release(lock)
    assert code == 1 and "Close it first" in text
    assert not list(data_dir.glob(".restore-*")) and not list(data_dir.glob("before-restore-*"))


def test_stopping_at_the_question_leaves_nothing_behind(saved, data_dir):
    backup, _ = saved

    def interrupted(_prompt):
        raise KeyboardInterrupt

    code = cli.main(["backup", "restore", str(backup)], output=lambda _t: None, ask=interrupted)
    assert code == 1
    assert not list(data_dir.glob(".restore-*"))


def test_old_leftovers_are_swept_at_start(data_dir, store, make_client):
    from app.backup.restore import sweep_leftovers

    make_client().app.state.engine.dispose()
    old, new = data_dir / ".restore-old", data_dir / ".restore-new"
    old.mkdir()
    new.mkdir()
    os.utime(old, (0, 0))
    sweep_leftovers(data_dir)
    assert not old.exists() and new.exists()  # a restore still checking is left alone


def test_an_earlier_restore_counts_as_data_of_its_own(
    saved, store, data_dir, tmp_path, monkeypatch, make_client
):
    """Its set-aside folder is encrypted with this folder's key, so the key mustn't be replaced."""
    backup, _ = saved
    phrase = master_key_to_phrase(store.get(key_name_for(data_dir)))
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", MemoryKeyStore())
    other = tmp_path / "other"
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(other))
    make_client().app.state.engine.dispose()  # its own key, no rows
    (other / "before-restore-2026-01-01-000000").mkdir()
    code, text = run(["backup", "restore", str(backup)], [phrase])
    assert code == 1 and "already holds data under a different key" in text


def test_a_running_home_base_holds_the_run_lock(data_dir, store):
    from app import run_lock

    with TestClient(create_app()) as client:  # runs the app's start-up and shut-down
        assert run_lock.try_lock(data_dir) is None
        client.app.state.engine.dispose()
    lock = run_lock.try_lock(data_dir)
    assert lock is not None
    run_lock.release(lock)


def test_a_move_that_fails_is_undone_cleanly(saved, data_dir, monkeypatch, make_client):
    """Like Windows refusing to move a file something holds open: nothing is left half-way."""
    from pathlib import Path

    backup, _ = saved
    real_rename = Path.rename

    def refuse_the_database(self, target):
        if self.name == "budget.db" and self.parent == data_dir:
            raise PermissionError(32, "in use")
        return real_rename(self, target)

    # Undo only this patch (monkeypatch.undo() would also drop the memory key store).
    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", refuse_the_database)
        code, text = run(["backup", "restore", str(backup)], ["RESTORE"])
    assert code == 1 and "put back as it was" in text
    assert not list(data_dir.glob("before-restore-*")) and not list(data_dir.glob(".restore-*"))
    make_client().app.state.engine.dispose()  # still starts on the data it had
