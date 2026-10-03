"""Encrypted files, for receipt photos (ADR-0003).

File layout::

    magic b"BBF" | version (1 byte, 0x01) | nonce (12 random bytes) | AES-256-GCM ciphertext + tag

The associated data is the 4-byte header plus the file's ID, so renaming or swapping two files
makes both fail to decrypt. Files are named with a random ID (no dates, merchants, or amounts in
file names) and saved in ``<data_dir>/receipts/``, readable only by this user on macOS/Linux.
"""

import os
import re
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.crypto._fs import ensure_private_dir, write_private_bytes
from app.crypto.errors import DecryptionError, FileTooLargeError

FILE_MAGIC = b"BBF"
FILE_FORMAT_V1 = 0x01
HEADER = FILE_MAGIC + bytes([FILE_FORMAT_V1])
NONCE_BYTES = 12
TAG_BYTES = 16
OVERHEAD = len(HEADER) + NONCE_BYTES + TAG_BYTES
DEFAULT_MAX_BYTES = 15 * 1024 * 1024  # a phone photo is usually 2-6 MB
RECEIPTS_DIRNAME = "receipts"
FILE_SUFFIX = ".bbf"
_FILE_ID = re.compile(r"^[0-9a-f]{32}$")


def _aad(file_id: str) -> bytes:
    return HEADER + file_id.encode("ascii")


def _check_size(size: int, max_bytes: int) -> None:
    if size > max_bytes:
        raise FileTooLargeError(
            f"That file is too big ({size / 1_048_576:.1f} MB). The limit is "
            f"{max_bytes / 1_048_576:.0f} MB."
        )


def encrypt_file(key: bytes, plaintext: bytes, file_id: str, *, max_bytes: int = DEFAULT_MAX_BYTES):
    """Encrypt one file's contents. Returns the bytes to save."""
    _check_size(len(plaintext), max_bytes)
    nonce = os.urandom(NONCE_BYTES)
    return HEADER + nonce + AESGCM(key).encrypt(nonce, plaintext, _aad(file_id))


def decrypt_file(key: bytes, blob: bytes, file_id: str, *, max_bytes: int = DEFAULT_MAX_BYTES):
    """Decrypt bytes made by :func:`encrypt_file` for the same ``file_id``."""
    _check_size(len(blob) - OVERHEAD, max_bytes)
    if len(blob) < OVERHEAD or blob[: len(HEADER)] != HEADER:
        raise DecryptionError("That file isn't a Budget Buddy encrypted file.")
    nonce = blob[len(HEADER) : len(HEADER) + NONCE_BYTES]
    try:
        return AESGCM(key).decrypt(nonce, blob[len(HEADER) + NONCE_BYTES :], _aad(file_id))
    except InvalidTag as exc:
        raise DecryptionError(
            "A saved file couldn't be decrypted. The encryption key may be wrong, or the file "
            "may have been changed or damaged."
        ) from exc


class EncryptedFileStore:
    """Saves and loads encrypted files in one folder, addressed by random IDs."""

    def __init__(self, directory: Path, key: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES):
        self.directory = Path(directory)
        self._key = key
        self.max_bytes = max_bytes

    def __repr__(self) -> str:  # never show the key
        return f"EncryptedFileStore({str(self.directory)!r})"

    @classmethod
    def for_receipts(cls, data_dir: Path, key: bytes, **kwargs) -> "EncryptedFileStore":
        return cls(Path(data_dir) / RECEIPTS_DIRNAME, key, **kwargs)

    def path_for(self, file_id: str) -> Path:
        if not isinstance(file_id, str) or not _FILE_ID.fullmatch(file_id):
            raise ValueError("Not a valid file ID.")  # also blocks "../" tricks
        return self.directory / (file_id + FILE_SUFFIX)

    def save(self, data: bytes) -> str:
        """Encrypt and save ``data``. Returns the new file's ID (store this, not a path)."""
        _check_size(len(data), self.max_bytes)
        file_id = uuid.uuid4().hex
        ensure_private_dir(self.directory)
        blob = encrypt_file(self._key, data, file_id, max_bytes=self.max_bytes)
        write_private_bytes(self.path_for(file_id), blob)
        return file_id

    def load(self, file_id: str) -> bytes:
        path = self.path_for(file_id)
        _check_size(path.stat().st_size - OVERHEAD, self.max_bytes)
        return decrypt_file(self._key, path.read_bytes(), file_id, max_bytes=self.max_bytes)

    def delete(self, file_id: str) -> None:
        self.path_for(file_id).unlink(missing_ok=True)
