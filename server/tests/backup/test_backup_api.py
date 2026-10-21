"""Backups in the dashboard: download one, and restore one at the next start (roadmap 24b)."""

import pytest
from sqlalchemy.orm import Session

from app.backup import pending, uploads
from app.backup.restore import RestoreStuckError
from app.crypto import MemoryKeyStore, key_name_for, master_key_to_phrase
from app.crypto import keystore as keystore_module
from app.models.ledger import Account

pytestmark = pytest.mark.real_migrations


@pytest.fixture
def store(monkeypatch):
    fresh = MemoryKeyStore()
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", fresh)
    return fresh


def names(client) -> list[str]:
    return sorted(a["name"] for a in client.get("/api/local/accounts").json())


def restart(client, make_client):
    client.app.state.engine.dispose()
    return make_client()


@pytest.fixture
def backup(store, make_account, client):
    """Bytes of a backup of a folder with one account ("Everyday"), then a second account added."""
    make_account(name="Everyday")
    response = client.get("/api/local/backup/file")
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="budget-buddy-backup-'
    )
    make_account(name="Added later")
    client.app.state.engine.dispose()  # as if closed: Windows won't move an open database
    return response.content


def test_status_says_which_key_and_nothing_waiting(client):
    status = client.get("/api/local/backup").json()
    assert len(status["key_fingerprint"]) == 32
    assert status["pending"] is None and status["restored_from"] is None


def test_a_download_leaves_no_copy_behind(backup, data_dir):
    assert backup[:3] == b"BBK"
    assert not list(data_dir.glob(".backup-*"))


def test_restore_finishes_at_the_next_start(backup, make_client, data_dir):
    client = make_client()
    waiting = client.post("/api/local/backup/restore", content=backup)
    assert waiting.status_code == 200, waiting.text
    assert client.get("/api/local/backup").json()["pending"]["receipts"] == 0
    assert names(client) == ["Added later", "Everyday"]  # nothing changes until the restart

    client = restart(client, make_client)
    assert names(client) == ["Everyday"]
    status = client.get("/api/local/backup").json()
    assert status["pending"] is None and "before-restore-" in status["restored_from"]
    client.app.state.engine.dispose()


def test_a_waiting_restore_can_be_cancelled(backup, make_client):
    client = make_client()
    client.post("/api/local/backup/restore", content=backup)
    assert client.delete("/api/local/backup/restore").status_code == 204
    client = restart(client, make_client)
    assert names(client) == ["Added later", "Everyday"]
    client.app.state.engine.dispose()


def test_a_damaged_backup_is_refused_and_nothing_waits(backup, make_client, data_dir):
    client = make_client()
    damaged = bytearray(backup)
    damaged[-40] ^= 1
    response = client.post("/api/local/backup/restore", content=bytes(damaged))
    assert response.status_code == 422 and response.json()["error"]["code"] == "backup_unusable"
    assert client.get("/api/local/backup").json()["pending"] is None
    assert not list(data_dir.glob(".restore-*"))
    client.app.state.engine.dispose()


def test_not_a_backup(client):
    response = client.post("/api/local/backup/restore", content=b"just some text")
    assert response.status_code == 422


def test_a_new_computer_restores_with_the_recovery_phrase(
    backup, store, data_dir, tmp_path, monkeypatch, make_client
):
    phrase = master_key_to_phrase(store.get(key_name_for(data_dir)))
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", MemoryKeyStore())
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(tmp_path / "new-computer"))
    client = make_client()  # Budget Buddy started once on the new computer: default categories only

    needed = client.post("/api/local/backup/restore", content=backup)
    assert needed.status_code == 409 and needed.json()["error"]["code"] == "recovery_phrase_needed"
    wrong = client.post(
        "/api/local/backup/restore", content=backup,
        headers={"X-Recovery-Phrase": master_key_to_phrase(bytes(32))},
    )  # fmt: skip
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "recovery_phrase_mismatch"
    ok = client.post(
        "/api/local/backup/restore", content=backup, headers={"X-Recovery-Phrase": phrase}
    )
    assert ok.status_code == 200, ok.text

    client = restart(client, make_client)
    assert names(client) == ["Everyday"]
    client.app.state.engine.dispose()


def test_another_keys_backup_never_replaces_data_of_its_own(
    backup, store, data_dir, tmp_path, monkeypatch, make_client
):
    phrase = master_key_to_phrase(store.get(key_name_for(data_dir)))
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", MemoryKeyStore())
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(tmp_path / "other"))
    client = make_client()
    with Session(client.app.state.engine) as session:
        session.add(Account(name="Mine", kind="checking"))
        session.commit()
    response = client.post(
        "/api/local/backup/restore", content=backup, headers={"X-Recovery-Phrase": phrase}
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "different_key_data"
    client.app.state.engine.dispose()


def test_not_for_other_computers(make_client):
    other = make_client(peer="192.168.1.30", base_url="http://192.168.1.20:8765")
    assert other.get("/api/local/backup/file").status_code in (401, 403, 404)


def test_another_website_cant_ask_for_a_backup(client, data_dir):
    response = client.get("/api/local/backup/file", headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403
    assert not list(data_dir.glob(".backup-*"))


def test_a_too_big_upload_is_refused_and_leaves_nothing(client, data_dir, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOAD_LIMIT_BYTES", 10)
    response = client.post("/api/local/backup/restore", content=b"x" * 100)
    assert response.status_code == 413
    assert not list(data_dir.glob(".restore-*"))


def new_computer_waiting(backup, store, data_dir, tmp_path, monkeypatch, make_client):
    """Another computer with ``backup`` waiting to restore: (its client, folder and vault)."""
    phrase = master_key_to_phrase(store.get(key_name_for(data_dir)))
    vault = MemoryKeyStore()
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", vault)
    new_dir = tmp_path / "new-computer"
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(new_dir))
    client = make_client()
    ok = client.post(
        "/api/local/backup/restore", content=backup, headers={"X-Recovery-Phrase": phrase}
    )
    assert ok.status_code == 200, ok.text
    return client, new_dir, vault


def test_cancel_removes_the_waiting_key(
    backup, store, data_dir, tmp_path, monkeypatch, make_client
):
    client, new_dir, vault = new_computer_waiting(
        backup, store, data_dir, tmp_path, monkeypatch, make_client
    )
    waiting_key = key_name_for(new_dir) + "-restore"
    assert vault.get(waiting_key) is not None
    assert client.delete("/api/local/backup/restore").status_code == 204
    assert vault.get(waiting_key) is None
    client.app.state.engine.dispose()


@pytest.mark.parametrize("left", [pending.PENDING_DIR, pending.PENDING_INFO])
def test_half_a_waiting_restore_is_cancelled_at_start(client, make_client, data_dir, left):
    client.app.state.engine.dispose()
    if left == pending.PENDING_DIR:
        (data_dir / left).mkdir()
    else:
        (data_dir / left).write_text('{"fingerprint": "00"}', encoding="ascii")
    client = make_client()
    assert not (data_dir / left).exists()
    client.app.state.engine.dispose()


def test_a_start_cut_short_after_the_swap_finishes_next_time(
    backup, store, data_dir, tmp_path, monkeypatch, make_client
):
    client, new_dir, vault = new_computer_waiting(
        backup, store, data_dir, tmp_path, monkeypatch, make_client
    )
    client.app.state.engine.dispose()

    def power_cut(*_args):
        raise KeyboardInterrupt  # stopped after the swap, before the key is kept

    with monkeypatch.context() as m:
        m.setattr(pending, "_store_key", power_cut)
        with pytest.raises(KeyboardInterrupt):
            pending.finish(new_dir, vault)
    assert (new_dir / pending.SWAPPING_INFO).exists()

    client = make_client()  # finishes the key step instead of restoring again
    assert names(client) == ["Everyday"]
    assert not (new_dir / pending.SWAPPING_INFO).exists()
    assert vault.get(key_name_for(new_dir) + "-restore") is None
    client.app.state.engine.dispose()


def test_a_start_cut_short_during_the_swap_stops(backup, make_client, data_dir):
    client = make_client()
    client.post("/api/local/backup/restore", content=backup)
    client.app.state.engine.dispose()
    (data_dir / pending.PENDING_INFO).replace(data_dir / pending.SWAPPING_INFO)  # as if cut short
    with pytest.raises(RestoreStuckError, match="stopped in the middle"):
        make_client()
    assert (data_dir / pending.PENDING_DIR).is_dir()  # nothing deleted or swapped again


def test_the_recovery_phrase_is_shown_on_this_computer(store, client, data_dir):
    response = client.post("/api/local/backup/recovery-phrase")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["phrase"] == master_key_to_phrase(store.get(key_name_for(data_dir)))


def test_the_recovery_phrase_needs_the_pages_token(client):
    response = client.post("/api/local/backup/recovery-phrase", headers={"X-CSRF-Token": "wrong"})
    assert response.status_code == 403
    assert "phrase" not in response.text


def test_no_recovery_phrase_without_the_right_key(store, client, data_dir):
    store.delete(key_name_for(data_dir))
    response = client.post("/api/local/backup/recovery-phrase")
    assert response.status_code == 409 and response.json()["error"]["code"] == "no_recovery_phrase"
