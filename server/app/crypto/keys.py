"""The master key and the purpose-specific keys derived from it (ADR-0003).

One random 32-byte master key per data folder lives in the key store. It is never used directly:
HKDF-SHA256 turns it into separate subkeys for database fields, the database file, receipt files,
and backups, so a mistake in one area can't weaken another.

A short *fingerprint* of the master key (not the key itself) is saved in the data folder as
``key-fingerprint``. It lets the Home Base notice, before touching any data, when the key on this
computer is missing or isn't the one the data was encrypted with, instead of quietly making a
new key and leaving the old data unreadable.
"""

import hmac
import logging
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.crypto._fs import write_private_bytes
from app.crypto.errors import KeyStoreError, MissingKeyError, WrongKeyError
from app.crypto.keystore import KeyStore, key_name_for

logger = logging.getLogger(__name__)

MASTER_KEY_BYTES = 32
FINGERPRINT_FILENAME = "key-fingerprint"
KEY_LOCK_FILENAME = "key.lock"

# HKDF "info" labels. Changing one changes the derived key, so these are fixed forever.
PURPOSE_DB_FIELDS = "db-fields"
PURPOSE_FILES = "files"
PURPOSE_BACKUP = "backup"
PURPOSE_DB_FILE = "db-file"  # the whole-database key (SQLCipher, ADR-0014); not "db-fields"
_PURPOSE_FINGERPRINT = "fingerprint"
_INFO_PREFIX = b"budget-buddy/v1/"


def generate_master_key() -> bytes:
    return secrets.token_bytes(MASTER_KEY_BYTES)


def derive_key(master_key: bytes, purpose: str) -> bytes:
    """A 32-byte subkey for one purpose (HKDF-SHA256, no salt: the master key is already random)."""
    _check_master_key(master_key)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_INFO_PREFIX + purpose.encode("ascii"),
    )
    return hkdf.derive(master_key)


def fingerprint(master_key: bytes) -> str:
    """A short, non-secret ID for a master key (derived one-way, so it reveals nothing)."""
    return derive_key(master_key, _PURPOSE_FINGERPRINT)[:16].hex()


@dataclass(frozen=True)
class DerivedKeys:
    """The subkeys the app uses. ``repr`` never shows key bytes."""

    db_fields: bytes = field(repr=False)
    files: bytes = field(repr=False)
    backup: bytes = field(repr=False)
    db_file: bytes = field(repr=False)

    @classmethod
    def from_master(cls, master_key: bytes) -> "DerivedKeys":
        return cls(
            db_fields=derive_key(master_key, PURPOSE_DB_FIELDS),
            files=derive_key(master_key, PURPOSE_FILES),
            backup=derive_key(master_key, PURPOSE_BACKUP),
            db_file=derive_key(master_key, PURPOSE_DB_FILE),
        )


def _check_master_key(master_key: bytes) -> None:
    if not isinstance(master_key, bytes) or len(master_key) != MASTER_KEY_BYTES:
        raise KeyStoreError("Budget Buddy's encryption key is the wrong size, so it can't be used.")


def fingerprint_path(data_dir: Path) -> Path:
    return data_dir / FINGERPRINT_FILENAME


def read_fingerprint(data_dir: Path) -> str | None:
    path = fingerprint_path(data_dir)
    if not path.is_file():
        return None
    return path.read_text(encoding="ascii").strip() or None


def save_fingerprint(data_dir: Path, fingerprint_hex: str) -> None:
    write_private_bytes(fingerprint_path(data_dir), (fingerprint_hex + "\n").encode())


def write_fingerprint(data_dir: Path, master_key: bytes) -> None:
    save_fingerprint(data_dir, fingerprint(master_key))


def matches_fingerprint(data_dir: Path, master_key: bytes) -> bool | None:
    """True/False if the folder has a fingerprint to compare with, ``None`` if it doesn't."""
    saved = read_fingerprint(data_dir)
    if saved is None:
        return None
    return hmac.compare_digest(saved, fingerprint(master_key))


MISSING_KEY_MESSAGE = (
    "Budget Buddy can't find the encryption key for your data folder ({data_dir}) on this "
    "computer. This can happen after reinstalling Windows or moving to a new computer. If you "
    "saved your recovery phrase, run:  python -m app recovery-phrase restore"
)
WRONG_KEY_MESSAGE = (
    "The encryption key on this computer doesn't match your data folder ({data_dir}), so Budget "
    "Buddy stopped before touching anything. If you saved your recovery phrase for this folder, "
    "run:  python -m app recovery-phrase restore"
)


def load_master_key(store: KeyStore, data_dir: Path) -> bytes | None:
    """The master key for ``data_dir`` from the store, or ``None`` if there isn't one."""
    key = store.get(key_name_for(data_dir))
    if key is not None:
        _check_master_key(key)
    return key


def load_or_create_master_key(store: KeyStore, data_dir: Path) -> bytes:
    """Load the folder's master key, creating one on first run.

    Refuses to create a new key if the folder already has data (a fingerprint or any database
    row), and refuses to use a key that doesn't match the fingerprint or, without one, can't
    decrypt the database. Either way the message says how to restore from the recovery phrase.

    Runs under a lock file, so two copies of Budget Buddy starting at once on first run can't
    each make a different key (one would overwrite the other and its data would be lost).
    """
    from app.db import _exclusive_lock  # imported here: app.db imports this package

    with _exclusive_lock(data_dir / KEY_LOCK_FILENAME):
        return _load_or_create_locked(store, data_dir)


def _load_or_create_locked(store: KeyStore, data_dir: Path) -> bytes:
    # Imported here: both import this module.
    from app.crypto import database_has_rows
    from app.crypto.key_check import key_opens_database

    key = load_master_key(store, data_dir)
    saved = read_fingerprint(data_dir)
    if key is None:
        # The fingerprint file can go missing; existing data is the real sign of a lost key.
        if saved is not None or database_has_rows(data_dir):
            raise MissingKeyError(MISSING_KEY_MESSAGE.format(data_dir=data_dir))
        key = generate_master_key()
        store.set(key_name_for(data_dir), key)
        write_fingerprint(data_dir, key)
        logger.warning(
            "Budget Buddy created a new encryption key for %s. Save your recovery phrase now "
            "(python -m app recovery-phrase show) so you can get your data back if this "
            "computer's password vault is ever lost.",
            data_dir,
        )
        return key
    if saved is None:
        if key_opens_database(data_dir, key) is False:
            raise WrongKeyError(WRONG_KEY_MESSAGE.format(data_dir=data_dir))
        write_fingerprint(data_dir, key)
    elif not hmac.compare_digest(saved, fingerprint(key)):
        raise WrongKeyError(WRONG_KEY_MESSAGE.format(data_dir=data_dir))
    return key
