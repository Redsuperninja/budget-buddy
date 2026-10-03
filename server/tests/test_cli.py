"""``python -m app recovery-phrase show|restore``."""

import pytest

from app import cli
from app.config import Settings
from app.crypto import MemoryKeyStore, key_name_for, master_key_to_phrase
from app.crypto import keystore as keystore_module
from app.crypto.keys import load_or_create_master_key, read_fingerprint
from app.main import create_app


@pytest.fixture
def store(monkeypatch):
    """A fresh memory key store standing in for this computer's password vault."""
    fresh = MemoryKeyStore()
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", fresh)
    return fresh


def _run(argv, answers):
    output: list[str] = []
    answers = iter(answers)
    code = cli.main(argv, output=output.append, ask=lambda _prompt: next(answers))
    return code, "\n".join(output)


def test_show_prints_phrase_after_warning(data_dir, store):
    create_app().state.engine.dispose()
    key = store.get(key_name_for(data_dir))
    code, out = _run(["recovery-phrase", "show"], [""])
    assert code == 0
    assert "Keep it private" in out
    assert master_key_to_phrase(key) in out


def test_show_can_be_cancelled(data_dir, store):
    create_app().state.engine.dispose()
    key = store.get(key_name_for(data_dir))
    code, out = _run(["recovery-phrase", "show"], ["q"])
    assert code == 1
    assert master_key_to_phrase(key) not in out


def test_show_before_first_run(data_dir, store):
    code, out = _run(["recovery-phrase", "show"], [])
    assert code == 1
    assert "Start Budget Buddy once" in out


def test_restore_after_vault_was_lost(data_dir, store, monkeypatch):
    app = create_app()
    app.state.engine.dispose()
    phrase = master_key_to_phrase(store.get(key_name_for(data_dir)))

    # Simulate a Windows reinstall: the vault is empty, the data folder is still there.
    lost = MemoryKeyStore()
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", lost)
    with pytest.raises(Exception, match="can't find the encryption key"):
        create_app()

    code, out = _run(["recovery-phrase", "restore"], [phrase.lower().replace("-", " ")])
    assert code == 0, out
    assert "Done" in out
    assert lost.get(key_name_for(data_dir)) == store.get(key_name_for(data_dir))
    create_app().state.engine.dispose()  # starts normally again


def test_restore_rejects_typo(data_dir, store):
    phrase = master_key_to_phrase(bytes(32))
    typo = ("2" if phrase[0] != "2" else "3") + phrase[1:]
    code, out = _run(["recovery-phrase", "restore"], [typo])
    assert code == 1
    assert "typo" in out
    assert store.get(key_name_for(data_dir)) is None


def test_restore_refuses_phrase_for_another_folder(data_dir, store):
    data_dir.mkdir()
    load_or_create_master_key(MemoryKeyStore(), data_dir)  # folder belongs to some other key
    code, out = _run(["recovery-phrase", "restore"], [master_key_to_phrase(bytes(32))])
    assert code == 1
    assert "isn't the one for this data folder" in out
    assert store.get(key_name_for(data_dir)) is None


def test_restore_asks_before_replacing_a_different_key(data_dir, store):
    data_dir.mkdir()
    store.set(key_name_for(data_dir), bytes(range(32)))
    phrase = master_key_to_phrase(bytes(32))

    code, out = _run(["recovery-phrase", "restore"], [phrase, ""])
    assert code == 1 and "Cancelled" in out
    assert store.get(key_name_for(data_dir)) == bytes(range(32))

    code, out = _run(["recovery-phrase", "restore"], [phrase, "REPLACE"])
    assert code == 0
    assert store.get(key_name_for(data_dir)) == bytes(32)
    assert read_fingerprint(data_dir) is not None


def test_restore_into_new_folder_writes_fingerprint(data_dir, store):
    code, _ = _run(["recovery-phrase", "restore"], [master_key_to_phrase(bytes(32))])
    assert code == 0
    assert read_fingerprint(data_dir) is not None
    assert Settings().data_dir == data_dir


def test_no_arguments_starts_server(monkeypatch):
    called = []
    monkeypatch.setattr("app.__main__.serve", lambda: called.append(True))
    assert cli.main([]) == 0
    assert called == [True]
