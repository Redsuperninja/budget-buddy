"""Encrypted database columns (ADR-0003).

Each value is stored as bytes::

    version (1 byte, 0x01) | nonce (12 random bytes) | AES-256-GCM ciphertext + 16-byte tag

The "associated data" is the version byte plus the column's ``table.column`` name, so a value
copied from one column into another (say a note pasted into ``accounts.last4``) fails to decrypt
instead of being shown in the wrong place. Any change to the bytes also fails to decrypt.

Accepted limitation (ADR-0003): a value is tied to its table and column, not its row. Swapping
two rows' values in the same column (say two accounts' ``last4``) still decrypts, with the values
swapped. Binding the row's primary key would need row context, which a ``TypeDecorator`` doesn't
get; and doing the swap needs write access to the database anyway.

Encrypted columns can't be searched, sorted, or compared in SQL (the same text encrypts
differently every time). Keep anything you need to query in a plain column.
"""

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Engine, LargeBinary, String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from app.crypto.errors import DecryptionError, EncryptionError

FIELD_FORMAT_V1 = 0x01
NONCE_BYTES = 12
TAG_BYTES = 16
_DIALECT_ATTR = "budget_buddy_field_cipher"


class FieldCipher:
    """Encrypts and decrypts single text values for one ``table.column`` at a time."""

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("Field key must be 32 bytes (AES-256).")
        self._aead = AESGCM(key)

    def __repr__(self) -> str:  # never show the key
        return "FieldCipher()"

    @staticmethod
    def _aad(context: str) -> bytes:
        return bytes([FIELD_FORMAT_V1]) + context.encode("utf-8")

    def encrypt(self, plaintext: str, context: str) -> bytes:
        nonce = os.urandom(NONCE_BYTES)
        sealed = self._aead.encrypt(nonce, plaintext.encode("utf-8"), self._aad(context))
        return bytes([FIELD_FORMAT_V1]) + nonce + sealed

    def decrypt(self, blob: bytes, context: str) -> str:
        if (
            not isinstance(blob, bytes | bytearray | memoryview)
            or len(blob) < 1 + NONCE_BYTES + TAG_BYTES
            or blob[0] != FIELD_FORMAT_V1
        ):
            raise DecryptionError(f"A saved value in {context} isn't in a format this app reads.")
        blob = bytes(blob)
        nonce, sealed = blob[1 : 1 + NONCE_BYTES], blob[1 + NONCE_BYTES :]
        try:
            return self._aead.decrypt(nonce, sealed, self._aad(context)).decode("utf-8")
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise DecryptionError(
                f"A saved value in {context} couldn't be decrypted. The encryption key may be "
                "wrong, or the database may have been changed or damaged."
            ) from exc


def set_field_cipher(engine: Engine, cipher: FieldCipher) -> None:
    """Give an engine the cipher its encrypted columns use.

    Stored on the engine's dialect (each engine has its own), because that's what SQLAlchemy
    hands to column types when it converts values. Tests with different folders and keys
    therefore never share a cipher.
    """
    setattr(engine.dialect, _DIALECT_ATTR, cipher)


def get_field_cipher(dialect: Dialect) -> FieldCipher | None:
    return getattr(dialect, _DIALECT_ATTR, None)


def _require_cipher(dialect: Dialect) -> FieldCipher:
    cipher = get_field_cipher(dialect)
    if cipher is None:
        raise EncryptionError(
            "The database was opened without its encryption key, so encrypted fields can't be "
            "read or saved. (Developers: create the engine with a field_cipher.)"
        )
    return cipher


class EncryptedString(TypeDecorator):
    """A text column stored encrypted. ``context`` must be the column's ``"table.column"``."""

    impl = LargeBinary
    cache_ok = True

    def __init__(self, context: str) -> None:
        super().__init__()
        self.context = context

    def process_bind_param(self, value: str | None, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{self.context} holds text, not {type(value).__name__}.")
        return _require_cipher(dialect).encrypt(value, self.context)

    def process_result_value(self, value: bytes | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return _require_cipher(dialect).decrypt(value, self.context)

    def process_literal_param(self, value, dialect):  # pragma: no cover - safety net
        raise EncryptionError("Encrypted values can't be written into SQL text.")

    @property
    def python_type(self) -> type:
        return str


def alembic_compare_type(
    _context, _inspected_column, _metadata_column, inspected_type, metadata_type
):
    """Alembic ``compare_type`` hook: an encrypted column stored as TEXT/VARCHAR/BLOB matches.

    Migration 0003 keeps these columns' declared types (SQLite stores the bytes as-is). Without
    this, ``alembic revision --autogenerate`` would propose a type change, which makes SQLite
    rebuild the table and can fire ``ON DELETE SET NULL`` on rows that point at it.
    Returns ``None`` for every other column, meaning "use Alembic's normal comparison".
    """
    if isinstance(metadata_type, EncryptedString):
        return not isinstance(inspected_type, String | LargeBinary)
    return None
