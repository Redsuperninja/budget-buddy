"""Encryption building blocks: keys, key stores, field cipher, files, recovery phrase."""

import stat
import sys
import threading
import time

import keyring
import keyring.backend
import keyring.backends.fail
import pytest

from app.config import Settings
from app.crypto import (
    DecryptionError,
    DerivedKeys,
    EncryptedFileStore,
    FieldCipher,
    FileTooLargeError,
    KeyringKeyStore,
    KeyStoreError,
    MemoryKeyStore,
    MissingKeyError,
    RecoveryPhraseError,
    WrongKeyError,
    decrypt_file,
    derive_key,
    encrypt_file,
    get_key_store,
    key_name_for,
    load_keys,
    load_or_create_master_key,
    master_key_to_phrase,
    phrase_to_master_key,
)
from app.crypto.keys import fingerprint, generate_master_key, read_fingerprint

KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))


# --- key derivation ---------------------------------------------------------------------------


def test_hkdf_subkeys_differ_and_are_stable():
    keys = DerivedKeys.from_master(KEY)
    assert len({keys.db_fields, keys.files, keys.backup, KEY}) == 4
    assert all(len(k) == 32 for k in (keys.db_fields, keys.files, keys.backup))
    assert derive_key(KEY, "files") == keys.files  # deterministic
    assert derive_key(OTHER_KEY, "files") != keys.files


def test_derived_keys_repr_hides_key_bytes():
    keys = DerivedKeys.from_master(KEY)
    assert repr(keys) == "DerivedKeys()"
    assert repr(FieldCipher(KEY)) == "FieldCipher()"


def test_master_key_must_be_32_bytes():
    with pytest.raises(KeyStoreError):
        derive_key(b"short", "files")


def test_generated_master_keys_are_random():
    assert generate_master_key() != generate_master_key()
    assert len(generate_master_key()) == 32


# --- key stores -------------------------------------------------------------------------------


def test_key_name_depends_on_folder(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert key_name_for(a) != key_name_for(b)
    assert key_name_for(a) == key_name_for(tmp_path / "x" / ".." / "a")
    assert str(tmp_path) not in key_name_for(a)  # only a hash of the path


def test_key_store_selection():
    assert isinstance(get_key_store("memory"), MemoryKeyStore)
    assert get_key_store("memory") is get_key_store("memory")  # shared within the process
    assert isinstance(get_key_store("keyring"), KeyringKeyStore)
    with pytest.raises(ValueError):
        get_key_store("disk")


def test_key_store_setting(monkeypatch):
    monkeypatch.delenv("BUDGET_BUDDY_KEY_STORE")
    assert Settings().insecure_test_keystore is True  # set by conftest for every test
    assert Settings().key_store == "keyring"
    monkeypatch.setenv("BUDGET_BUDDY_KEY_STORE", "memory")
    assert Settings().key_store == "memory"
    monkeypatch.setenv("BUDGET_BUDDY_KEY_STORE", "plaintext-file")
    with pytest.raises(ValueError):
        Settings()


class _DictKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.passwords: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.passwords.get((service, username))

    def set_password(self, service, username, password):
        self.passwords[(service, username)] = password

    def delete_password(self, service, username):
        self.passwords.pop((service, username), None)


@pytest.fixture
def fake_keyring():
    previous = keyring.get_keyring()
    backend = _DictKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def test_keyring_store_round_trip(fake_keyring):
    store = KeyringKeyStore()
    assert store.get("data-x") is None
    store.set("data-x", KEY)
    assert store.get("data-x") == KEY
    (service, username), stored = next(iter(fake_keyring.passwords.items()))
    assert (service, username) == ("budget-buddy", "data-x")
    assert stored != KEY.hex()  # base64, never raw


def test_keyring_store_damaged_entry(fake_keyring):
    fake_keyring.passwords[("budget-buddy", "data-x")] = "not base64!!"
    with pytest.raises(KeyStoreError, match="damaged"):
        KeyringKeyStore().get("data-x")


def test_no_os_vault_gives_clear_error():
    previous = keyring.get_keyring()
    keyring.set_keyring(keyring.backends.fail.Keyring())
    try:
        with pytest.raises(KeyStoreError, match="password vault") as raised:
            KeyringKeyStore().get("data-x")
        # Don't point everyday users at the test-only memory key store (security review H1).
        assert "memory" not in str(raised.value).lower()
        assert "KEY_STORE" not in str(raised.value)
    finally:
        keyring.set_keyring(previous)


# --- memory key store guard rails (security review H1) ---------------------------------------


def test_memory_key_store_needs_the_test_only_switch(monkeypatch, tmp_path):
    monkeypatch.delenv("BUDGET_BUDDY_INSECURE_TEST_KEYSTORE")
    with pytest.raises(KeyStoreError, match="only for automated tests"):
        Settings(key_store="memory", data_dir=tmp_path)
    monkeypatch.setenv("BUDGET_BUDDY_INSECURE_TEST_KEYSTORE", "0")
    with pytest.raises(KeyStoreError):
        Settings(key_store="memory", data_dir=tmp_path)
    assert Settings(key_store="keyring", data_dir=tmp_path).key_store == "keyring"
    monkeypatch.setenv("BUDGET_BUDDY_INSECURE_TEST_KEYSTORE", "1")
    assert Settings(key_store="memory", data_dir=tmp_path).key_store == "memory"


@pytest.fixture
def fresh_memory_store(monkeypatch):
    """An empty memory store, like a brand-new process."""
    import app.crypto.keystore as keystore_module

    fresh = MemoryKeyStore()
    monkeypatch.setattr(keystore_module, "_MEMORY_STORE", fresh)
    return fresh


def test_memory_key_store_works_on_a_fresh_folder(tmp_path, fresh_memory_store):
    settings = Settings(key_store="memory", data_dir=tmp_path)
    first = load_keys(settings)
    assert load_keys(settings) == first  # same process, same folder: key reused


def test_memory_key_store_refuses_folder_with_a_key_fingerprint(tmp_path, fresh_memory_store):
    load_or_create_master_key(MemoryKeyStore(), tmp_path)  # folder already has a key elsewhere
    with pytest.raises(KeyStoreError, match="new, empty data folder"):
        load_keys(Settings(key_store="memory", data_dir=tmp_path))
    assert fresh_memory_store.get(key_name_for(tmp_path)) is None


def test_memory_key_store_refuses_folder_with_existing_data(tmp_path, fresh_memory_store):
    import sqlite3

    connection = sqlite3.connect(tmp_path / "budget.db")
    connection.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, last4 TEXT)")
    connection.execute("INSERT INTO accounts (last4) VALUES ('4821')")
    connection.commit()
    connection.close()
    with pytest.raises(KeyStoreError, match="new, empty data folder"):
        load_keys(Settings(key_store="memory", data_dir=tmp_path))
    assert read_fingerprint(tmp_path) is None  # nothing was changed


def test_memory_key_store_allows_empty_database(tmp_path, fresh_memory_store):
    import sqlite3

    connection = sqlite3.connect(tmp_path / "budget.db")
    connection.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, last4 TEXT)")
    connection.execute("CREATE TABLE alembic_version (version_num TEXT)")
    connection.execute("INSERT INTO alembic_version VALUES ('0002')")
    connection.commit()
    connection.close()
    load_keys(Settings(key_store="memory", data_dir=tmp_path))


def test_load_keys_uses_keyring_by_default(tmp_path, monkeypatch, fake_keyring):
    monkeypatch.delenv("BUDGET_BUDDY_KEY_STORE")
    keys = load_keys(Settings(data_dir=tmp_path))
    stored = KeyringKeyStore().get(key_name_for(tmp_path))
    assert keys == DerivedKeys.from_master(stored)


# --- master key lifecycle ---------------------------------------------------------------------


def test_master_key_created_once_then_reused(tmp_path):
    store = MemoryKeyStore()
    first = load_or_create_master_key(store, tmp_path)
    assert load_or_create_master_key(store, tmp_path) == first
    assert read_fingerprint(tmp_path) == fingerprint(first)
    assert first.hex() not in (tmp_path / "key-fingerprint").read_text()


def test_concurrent_first_runs_agree_on_one_key(tmp_path):
    """Two copies starting at once must not each create (and save) a different key."""
    store = MemoryKeyStore()
    original_set = store.set

    def slow_set(name, key):
        time.sleep(0.05)  # widen the window between "no key yet" and "key saved"
        original_set(name, key)

    store.set = slow_set
    results, errors = [], []

    def start():
        try:
            results.append(load_or_create_master_key(store, tmp_path))
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=start) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(set(results)) == 1
    assert results[0] == store.get(key_name_for(tmp_path))


def test_missing_key_for_existing_data_is_not_silently_replaced(tmp_path):
    load_or_create_master_key(MemoryKeyStore(), tmp_path)
    with pytest.raises(MissingKeyError, match="recovery-phrase restore"):
        load_or_create_master_key(MemoryKeyStore(), tmp_path)  # e.g. after a Windows reinstall


def test_wrong_key_for_folder_is_refused(tmp_path):
    load_or_create_master_key(MemoryKeyStore(), tmp_path)
    other = MemoryKeyStore()
    other.set(key_name_for(tmp_path), OTHER_KEY)
    with pytest.raises(WrongKeyError):
        load_or_create_master_key(other, tmp_path)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_fingerprint_file_is_private_on_posix(tmp_path):
    load_or_create_master_key(MemoryKeyStore(), tmp_path)
    assert stat.S_IMODE((tmp_path / "key-fingerprint").stat().st_mode) == 0o600


# --- field cipher -----------------------------------------------------------------------------


def test_field_round_trip_and_random_nonce():
    cipher = FieldCipher(KEY)
    a = cipher.encrypt("Card ending 1234 ✓", "accounts.notes")
    b = cipher.encrypt("Card ending 1234 ✓", "accounts.notes")
    assert a != b  # fresh nonce every time
    assert a[0] == 1  # version byte
    assert b"1234" not in a
    assert cipher.decrypt(a, "accounts.notes") == "Card ending 1234 ✓"
    assert cipher.decrypt(cipher.encrypt("", "accounts.notes"), "accounts.notes") == ""


def test_field_swapped_column_fails():
    cipher = FieldCipher(KEY)
    blob = cipher.encrypt("1234", "accounts.last4")
    with pytest.raises(DecryptionError):
        cipher.decrypt(blob, "accounts.notes")


@pytest.mark.parametrize("position", [0, 5, 20, -1])
def test_field_tampering_fails(position):
    cipher = FieldCipher(KEY)
    blob = bytearray(cipher.encrypt("hello", "transactions.notes"))
    blob[position] ^= 0x01
    with pytest.raises(DecryptionError):
        cipher.decrypt(bytes(blob), "transactions.notes")


def test_field_wrong_key_fails():
    blob = FieldCipher(KEY).encrypt("hello", "transactions.notes")
    with pytest.raises(DecryptionError):
        FieldCipher(OTHER_KEY).decrypt(blob, "transactions.notes")


def test_field_truncated_value_fails():
    with pytest.raises(DecryptionError):
        FieldCipher(KEY).decrypt(b"\x01short", "transactions.notes")


def test_field_error_messages_hold_no_data():
    blob = FieldCipher(KEY).encrypt("secret note", "transactions.notes")
    with pytest.raises(DecryptionError) as info:
        FieldCipher(OTHER_KEY).decrypt(blob, "transactions.notes")
    assert "secret" not in str(info.value)


# --- files ------------------------------------------------------------------------------------

FILE_ID = "0123456789abcdef0123456789abcdef"


def test_file_round_trip():
    data = b"\x89PNG fake receipt image" * 100
    blob = encrypt_file(KEY, data, FILE_ID)
    assert blob[:4] == b"BBF\x01"
    assert b"receipt" not in blob
    assert decrypt_file(KEY, blob, FILE_ID) == data


def test_file_tampering_fails():
    blob = bytearray(encrypt_file(KEY, b"image bytes", FILE_ID))
    blob[-3] ^= 0xFF
    with pytest.raises(DecryptionError):
        decrypt_file(KEY, bytes(blob), FILE_ID)


def test_file_swapped_id_fails():
    blob = encrypt_file(KEY, b"image bytes", FILE_ID)
    with pytest.raises(DecryptionError):
        decrypt_file(KEY, blob, "f" * 32)


def test_file_wrong_key_fails():
    blob = encrypt_file(KEY, b"image bytes", FILE_ID)
    with pytest.raises(DecryptionError):
        decrypt_file(OTHER_KEY, blob, FILE_ID)


def test_file_not_ours_fails():
    with pytest.raises(DecryptionError):
        decrypt_file(KEY, b"JPEG" + b"\x00" * 40, FILE_ID)


def test_file_size_limit():
    with pytest.raises(FileTooLargeError, match="too big"):
        encrypt_file(KEY, b"x" * 11, FILE_ID, max_bytes=10)


def test_file_store_saves_encrypted_with_random_names(tmp_path):
    store = EncryptedFileStore.for_receipts(tmp_path, KEY)
    first = store.save(b"receipt one")
    second = store.save(b"receipt one")
    assert first != second
    path = tmp_path / "receipts" / f"{first}.bbf"
    assert path.is_file()
    assert b"receipt one" not in path.read_bytes()
    assert store.load(first) == b"receipt one"
    assert [p.name for p in (tmp_path / "receipts").iterdir() if p.name.endswith(".tmp")] == []
    store.delete(first)
    assert not path.exists()
    assert KEY.hex() not in repr(store)


def test_file_store_rejects_swapped_files(tmp_path):
    store = EncryptedFileStore.for_receipts(tmp_path, KEY)
    a, b = store.save(b"a"), store.save(b"b")
    pa, pb = store.path_for(a), store.path_for(b)
    data_a, data_b = pa.read_bytes(), pb.read_bytes()
    pa.write_bytes(data_b)
    pb.write_bytes(data_a)
    with pytest.raises(DecryptionError):
        store.load(a)


def test_file_store_size_limit(tmp_path):
    store = EncryptedFileStore.for_receipts(tmp_path, KEY, max_bytes=10)
    with pytest.raises(FileTooLargeError):
        store.save(b"x" * 11)
    assert not (tmp_path / "receipts").exists() or not any((tmp_path / "receipts").iterdir())


@pytest.mark.parametrize("bad_id", ["../budget", "..\\x", "", "A" * 32, "0" * 31, None])
def test_file_store_rejects_bad_ids(tmp_path, bad_id):
    with pytest.raises(ValueError):
        EncryptedFileStore.for_receipts(tmp_path, KEY).path_for(bad_id)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_file_store_files_are_private_on_posix(tmp_path):
    store = EncryptedFileStore.for_receipts(tmp_path, KEY)
    file_id = store.save(b"x")
    assert stat.S_IMODE(store.path_for(file_id).stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "receipts").stat().st_mode) == 0o700


# --- recovery phrase --------------------------------------------------------------------------


def test_recovery_phrase_round_trip():
    key = generate_master_key()
    phrase = master_key_to_phrase(key)
    groups = phrase.split("-")
    assert len(groups) == 16 and all(len(g) == 4 for g in groups)
    assert phrase_to_master_key(phrase) == key


def test_recovery_phrase_is_forgiving_about_formatting():
    phrase = master_key_to_phrase(KEY)
    sloppy = " ".join(phrase.lower().split("-")).replace("0", "o").replace("1", "l")
    assert phrase_to_master_key("  " + sloppy + "\n") == KEY


def test_recovery_phrase_checksum_catches_a_typo():
    phrase = master_key_to_phrase(KEY)
    i = 7
    replacement = "2" if phrase[i] != "2" else "3"
    with pytest.raises(RecoveryPhraseError, match="typo"):
        phrase_to_master_key(phrase[:i] + replacement + phrase[i + 1 :])


def test_recovery_phrase_checksum_catches_swapped_characters():
    phrase = master_key_to_phrase(KEY).replace("-", "")
    i = next(i for i in range(len(phrase) - 1) if phrase[i] != phrase[i + 1])
    swapped = phrase[:i] + phrase[i + 1] + phrase[i] + phrase[i + 2 :]
    with pytest.raises(RecoveryPhraseError):
        phrase_to_master_key(swapped)


def test_recovery_phrase_wrong_length_and_bad_characters():
    phrase = master_key_to_phrase(KEY)
    with pytest.raises(RecoveryPhraseError, match="16 groups"):
        phrase_to_master_key(phrase[:-5])
    with pytest.raises(RecoveryPhraseError, match="can't be in"):
        phrase_to_master_key("U" + phrase[1:])


def test_recovery_phrase_error_does_not_echo_the_character():
    """Security review L2: report only where the bad character is, never the character."""
    phrase = master_key_to_phrase(KEY).replace("-", "")
    bad = phrase[:4] + "#" + phrase[5:]
    with pytest.raises(RecoveryPhraseError, match="Character 5 can't be in") as raised:
        phrase_to_master_key(bad)
    assert "#" not in str(raised.value)
