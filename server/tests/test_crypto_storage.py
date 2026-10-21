"""Encryption of stored data: field cipher, files, recovery phrase."""

import stat
import sys

import pytest
from crypto_helpers import KEY, OTHER_KEY

from app.crypto import (
    DecryptionError,
    EncryptedFileStore,
    FieldCipher,
    FileTooLargeError,
    RecoveryPhraseError,
    decrypt_file,
    encrypt_file,
    master_key_to_phrase,
    phrase_to_master_key,
)
from app.crypto.keys import generate_master_key

pytestmark = pytest.mark.real_migrations

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
