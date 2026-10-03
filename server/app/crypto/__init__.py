"""Encryption at rest (ADR-0003): master key, derived keys, encrypted fields and files."""

import logging

from app.config import Settings
from app.crypto.errors import (
    DecryptionError,
    EncryptionError,
    FileTooLargeError,
    KeyStoreError,
    MissingKeyError,
    RecoveryPhraseError,
    WrongKeyError,
)
from app.crypto.fields import EncryptedString, FieldCipher, get_field_cipher, set_field_cipher
from app.crypto.files import EncryptedFileStore, decrypt_file, encrypt_file
from app.crypto.keys import DerivedKeys, derive_key, load_or_create_master_key
from app.crypto.keystore import (
    KeyringKeyStore,
    KeyStore,
    MemoryKeyStore,
    get_key_store,
    key_name_for,
)
from app.crypto.recovery import master_key_to_phrase, phrase_to_master_key

logger = logging.getLogger(__name__)


def load_keys(settings: Settings) -> DerivedKeys:
    """Load (or on first run create) the data folder's master key and derive the app's keys.

    The data folder must already exist. The master key itself isn't kept around afterwards.
    """
    if settings.key_store == "memory":
        logger.warning(
            "Encryption key is kept in memory only (BUDGET_BUDDY_KEY_STORE=memory). This is for "
            "automated tests: data saved now can't be read after Budget Buddy restarts."
        )
    store = get_key_store(settings.key_store)
    return DerivedKeys.from_master(load_or_create_master_key(store, settings.data_dir))


__all__ = [
    "DecryptionError",
    "DerivedKeys",
    "EncryptedFileStore",
    "EncryptedString",
    "EncryptionError",
    "FieldCipher",
    "FileTooLargeError",
    "KeyStore",
    "KeyStoreError",
    "KeyringKeyStore",
    "MemoryKeyStore",
    "MissingKeyError",
    "RecoveryPhraseError",
    "WrongKeyError",
    "decrypt_file",
    "derive_key",
    "encrypt_file",
    "get_field_cipher",
    "get_key_store",
    "key_name_for",
    "load_keys",
    "load_or_create_master_key",
    "master_key_to_phrase",
    "phrase_to_master_key",
    "set_field_cipher",
]
