"""``python -m app recovery-phrase show|restore``."""

import pytest

from app import cli
from app.config import Settings
from app.crypto import EncryptionError, MemoryKeyStore, key_name_for, master_key_to_phrase
from app.crypto import keystore as keystore_module
from app.crypto.keys import fingerprint_path, load_or_create_master_key, read_fingerprint
from app.main import create_app


@pytest.fixture
def store(monkeypatch):
    """A fresh memory key store standing in for this computer's password vault."""
    fresh = MemoryKeyStore()
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", fresh)
    return fresh


@pytest.fixture(autouse=True)
def terminal(monkeypatch):
    """Pretend output goes to a terminal window (pytest captures it, so it normally doesn't)."""
    monkeypatch.setattr(cli, "_stdout_is_terminal", lambda: True)


def _run(argv, answers):
    output: list[str] = []
    answers = iter(answers)

    def answer(_prompt):
        return next(answers)

    code = cli.main(argv, output=output.append, ask=answer, ask_secret=answer)
    return code, "\n".join(output)


def test_show_prints_phrase_after_warning(data_dir, store):
    create_app().state.engine.dispose()
    key = store.get(key_name_for(data_dir))
    code, out = _run(["recovery-phrase", "show"], ["SHOW"])
    assert code == 0
    assert "Keep it private" in out
    assert master_key_to_phrase(key) in out


@pytest.mark.parametrize("answer", ["", "q", "yes", "no", "y", "show", "Show", "SHOW please"])
def test_show_needs_exactly_show(data_dir, store, answer):
    """Security review M2: only typing SHOW displays the phrase; "yes" must not."""
    create_app().state.engine.dispose()
    key = store.get(key_name_for(data_dir))
    code, out = _run(["recovery-phrase", "show"], [answer])
    assert code == 1
    assert "Cancelled" in out
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
    # (With the keyring this is MissingKeyError; the memory store refuses non-empty folders.)
    with pytest.raises(EncryptionError):
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


# --- keeping the phrase out of files and scrollback (security review L2) ---------------------


def test_show_refuses_when_output_is_not_a_terminal(data_dir, store, monkeypatch):
    create_app().state.engine.dispose()
    key = store.get(key_name_for(data_dir))
    monkeypatch.setattr(cli, "_stdout_is_terminal", lambda: False)
    code, out = _run(["recovery-phrase", "show"], ["SHOW"])
    assert code == 1
    assert "only shown in a terminal" in out
    assert master_key_to_phrase(key) not in out

    code, out = _run(["recovery-phrase", "show", "--force"], ["SHOW"])
    assert code == 0
    assert master_key_to_phrase(key) in out


def test_show_refuses_key_that_does_not_match_the_folder(data_dir, store):
    create_app().state.engine.dispose()
    key = store.get(key_name_for(data_dir))
    fingerprint_path(data_dir).write_text("0" * 32 + "\n", encoding="ascii")
    code, out = _run(["recovery-phrase", "show"], ["SHOW"])
    assert code == 1
    assert "doesn't match your data folder" in out
    assert master_key_to_phrase(key) not in out


def test_restore_reads_phrase_without_echo(data_dir, store, monkeypatch):
    phrase = master_key_to_phrase(bytes(32))
    prompts = []

    def fake_getpass(prompt):
        prompts.append(prompt)
        return phrase

    def no_visible_input(_prompt):
        raise AssertionError("the phrase must not be read with input()")

    monkeypatch.setattr(cli.getpass, "getpass", fake_getpass)
    output: list[str] = []
    code = cli.restore_phrase(Settings(), output.append, ask=no_visible_input)
    assert code == 0
    assert prompts == ["Recovery phrase: "]
    assert phrase not in "\n".join(output)
    assert store.get(key_name_for(data_dir)) == bytes(32)
