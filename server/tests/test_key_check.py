"""The key check inside the database, for when the key-fingerprint file is gone (issue #26)."""

import sqlite3

import pytest
from crypto_helpers import KEY, OTHER_KEY

from app import cli
from app.config import Settings
from app.crypto import (
    FieldCipher,
    KeyCheckError,
    MemoryKeyStore,
    MissingKeyError,
    WrongKeyError,
    key_name_for,
    master_key_to_phrase,
)
from app.crypto import keystore as keystore_module
from app.crypto.key_check import encrypted_samples, key_opens_database
from app.crypto.keys import (
    PURPOSE_DB_FIELDS,
    derive_key,
    fingerprint,
    fingerprint_path,
    load_or_create_master_key,
    read_fingerprint,
)


def _make_db(folder, last4):
    """A ``budget.db`` with one account whose ``last4`` is ``last4`` (bytes or text) or NULL."""
    connection = sqlite3.connect(folder / "budget.db")
    connection.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, last4 BLOB)")
    connection.execute("INSERT INTO accounts (last4) VALUES (?)", (last4,))
    connection.commit()
    connection.close()


def _encrypted(master_key, text="1234"):
    return FieldCipher(derive_key(master_key, PURPOSE_DB_FIELDS)).encrypt(text, "accounts.last4")


def _store_with(folder, key):
    store = MemoryKeyStore()
    store.set(key_name_for(folder), key)
    return store


def test_only_the_right_key_opens_the_database(tmp_path):
    _make_db(tmp_path, _encrypted(KEY))
    assert [context for _, context in encrypted_samples(tmp_path)] == ["accounts.last4"]
    assert key_opens_database(tmp_path, KEY) is True
    assert key_opens_database(tmp_path, OTHER_KEY) is False


def test_one_damaged_value_does_not_lock_out_the_right_key(tmp_path):
    damaged = bytearray(_encrypted(KEY))
    damaged[-1] ^= 0xFF
    _make_db(tmp_path, bytes(damaged))
    connection = sqlite3.connect(tmp_path / "budget.db")
    connection.execute("INSERT INTO accounts (last4) VALUES (?)", (_encrypted(KEY),))
    connection.commit()
    connection.close()
    assert key_opens_database(tmp_path, KEY) is True
    assert key_opens_database(tmp_path, OTHER_KEY) is False


def test_unreadable_database_is_not_treated_as_nothing_to_check(tmp_path):
    """Security review: a wrong key must not be accepted just because the check couldn't run."""
    (tmp_path / "budget.db").write_bytes(b"not a database at all, but long enough to try")
    with pytest.raises(KeyCheckError, match="couldn't read the database"):
        key_opens_database(tmp_path, KEY)
    with pytest.raises(KeyCheckError):
        load_or_create_master_key(_store_with(tmp_path, OTHER_KEY), tmp_path)
    assert read_fingerprint(tmp_path) is None


def test_locked_database_is_not_treated_as_nothing_to_check(tmp_path):
    _make_db(tmp_path, _encrypted(KEY))
    writer = sqlite3.connect(tmp_path / "budget.db", timeout=0)
    writer.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(KeyCheckError):
            key_opens_database(tmp_path, OTHER_KEY)
    finally:
        writer.rollback()
        writer.close()


@pytest.mark.parametrize("last4", [None, "1234"], ids=["null", "text-from-before-0003"])
def test_nothing_to_test_without_an_encrypted_value(tmp_path, last4):
    _make_db(tmp_path, last4)
    assert key_opens_database(tmp_path, KEY) is None


def test_nothing_to_test_without_a_database(tmp_path):
    assert key_opens_database(tmp_path, KEY) is None
    (tmp_path / "budget.db").write_bytes(b"")
    assert key_opens_database(tmp_path, KEY) is None


def test_no_new_key_over_existing_data_when_fingerprint_and_vault_are_gone(tmp_path):
    _make_db(tmp_path, _encrypted(KEY))
    with pytest.raises(MissingKeyError, match="recovery-phrase restore"):
        load_or_create_master_key(MemoryKeyStore(), tmp_path)
    assert read_fingerprint(tmp_path) is None


def test_no_new_key_over_unencrypted_rows_either(tmp_path):
    _make_db(tmp_path, None)
    with pytest.raises(MissingKeyError):
        load_or_create_master_key(MemoryKeyStore(), tmp_path)


def test_wrong_key_refused_when_fingerprint_is_gone(tmp_path):
    _make_db(tmp_path, _encrypted(KEY))
    with pytest.raises(WrongKeyError):
        load_or_create_master_key(_store_with(tmp_path, OTHER_KEY), tmp_path)
    assert read_fingerprint(tmp_path) is None  # not "repaired" to the wrong key


@pytest.fixture
def vault(monkeypatch):
    """An empty memory key store standing in for this computer's password vault."""
    fresh = MemoryKeyStore()
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", fresh)
    return fresh


def _restore(folder, key):
    output: list[str] = []
    settings = Settings(data_dir=folder, key_store="memory")
    code = cli.restore_phrase(
        settings, output.append, ask=lambda _: "", ask_secret=lambda _: master_key_to_phrase(key)
    )
    return code, "\n".join(output)


def test_restore_refuses_wrong_phrase_when_fingerprint_is_gone(tmp_path, vault):
    _make_db(tmp_path, _encrypted(KEY))
    code, out = _restore(tmp_path, OTHER_KEY)
    assert code == 1
    assert "isn't the one for this data folder" in out
    assert vault.get(key_name_for(tmp_path)) is None


def test_restore_accepts_right_phrase_when_fingerprint_is_gone(tmp_path, vault):
    _make_db(tmp_path, _encrypted(KEY))
    code, out = _restore(tmp_path, KEY)
    assert code == 0, out
    assert vault.get(key_name_for(tmp_path)) == KEY
    assert read_fingerprint(tmp_path) == fingerprint(KEY)


def test_show_refuses_key_that_cannot_open_the_database(tmp_path, vault):
    _make_db(tmp_path, _encrypted(KEY))
    vault.set(key_name_for(tmp_path), OTHER_KEY)
    output: list[str] = []
    settings = Settings(data_dir=tmp_path, key_store="memory")
    assert cli.show_phrase(settings, output.append, ask=lambda _: "SHOW", force=True) == 1
    assert master_key_to_phrase(OTHER_KEY) not in "\n".join(output)


def test_right_key_rewrites_a_missing_fingerprint(tmp_path):
    _make_db(tmp_path, _encrypted(KEY))
    assert load_or_create_master_key(_store_with(tmp_path, KEY), tmp_path) == KEY
    assert read_fingerprint(tmp_path) == fingerprint(KEY)
    fingerprint_path(tmp_path).unlink()
    assert load_or_create_master_key(_store_with(tmp_path, KEY), tmp_path) == KEY
