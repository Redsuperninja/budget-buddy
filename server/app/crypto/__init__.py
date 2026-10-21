"""Encryption at rest (ADR-0003): master key, derived keys, encrypted fields and files."""

import logging
import sqlite3
from pathlib import Path

from app.config import Settings
from app.crypto.errors import (
    DecryptionError,
    EncryptionError,
    FileTooLargeError,
    KeyCheckError,
    KeyStoreError,
    MissingKeyError,
    RecoveryPhraseError,
    WrongKeyError,
)
from app.crypto.fields import EncryptedString, FieldCipher, get_field_cipher, set_field_cipher
from app.crypto.files import EncryptedFileStore, decrypt_file, encrypt_file
from app.crypto.keys import (
    DerivedKeys,
    derive_key,
    load_master_key,
    load_or_create_master_key,
    read_fingerprint,
)
from app.crypto.keystore import (
    KeyringKeyStore,
    KeyStore,
    MemoryKeyStore,
    get_key_store,
    key_name_for,
)
from app.crypto.recovery import master_key_to_phrase, phrase_to_master_key

logger = logging.getLogger(__name__)


MEMORY_STORE_IN_USE_MESSAGE = (
    "BUDGET_BUDDY_KEY_STORE=memory can only be used with a new, empty data folder, and {data_dir} "
    "already has data or an encryption key. Nothing was changed."
)


def database_has_rows(data_dir: Path, ignore: frozenset[str] = frozenset()) -> bool:
    """True if ``budget.db`` exists and any of its tables (other than Alembic's and ``ignore``)
    holds a row. A database that can't be read counts as having rows, so nothing treats it as
    empty."""
    from app.db import open_read_only  # imported here: app.db imports this package

    path = data_dir / "budget.db"
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        with open_read_only(path) as connection:
            tables = [
                name
                for (name,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
                )
                if name not in ignore
            ]
            quoted = ('"' + name.replace('"', '""') + '"' for name in tables)
            return any(connection.execute(f"SELECT 1 FROM {q} LIMIT 1").fetchone() for q in quoted)
    except sqlite3.DatabaseError:
        return True


def _check_memory_store_folder(store: KeyStore, data_dir: Path) -> None:
    """Memory mode may only ever start a fresh, throwaway data folder (security review H1).

    Taking over a folder that already has data or a key fingerprint would encrypt (or lock) that
    data under a key that disappears when the process ends. A folder this same process started
    (its key is already in the memory store) is fine.
    """
    if load_master_key(store, data_dir) is not None:
        return
    if read_fingerprint(data_dir) is not None or database_has_rows(data_dir):
        raise KeyStoreError(MEMORY_STORE_IN_USE_MESSAGE.format(data_dir=data_dir))


def load_keys(settings: Settings) -> DerivedKeys:
    """Load (or on first run create) the data folder's master key and derive the app's keys.

    The data folder must already exist. The master key itself isn't kept around afterwards.
    """
    store = get_key_store(settings.key_store)
    if settings.key_store == "memory":
        _check_memory_store_folder(store, settings.data_dir)
        logger.warning(
            "Encryption key is kept in memory only (BUDGET_BUDDY_KEY_STORE=memory). This is for "
            "automated tests: data saved now can't be read after Budget Buddy restarts."
        )
    return DerivedKeys.from_master(load_or_create_master_key(store, settings.data_dir))


__all__ = [
    "DecryptionError",
    "DerivedKeys",
    "EncryptedFileStore",
    "EncryptedString",
    "EncryptionError",
    "FieldCipher",
    "FileTooLargeError",
    "KeyCheckError",
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
