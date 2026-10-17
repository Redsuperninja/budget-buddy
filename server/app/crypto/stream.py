"""Encrypting one large file in chunks, for backups (ADR-0012).

File layout::

    header: magic b"BBK" | version 0x01 | key fingerprint (16 bytes) | salt (16 random bytes)
    chunks: AES-256-GCM of each 1 MiB of contents (the last shorter, maybe empty) + 16-byte tag

Each file has its own key: HKDF-SHA256 of the backup key with the file's salt, so nonces can't
repeat across files. A chunk's nonce is its number (11 bytes) and a "last chunk" flag (1 byte);
every chunk authenticates the whole header. So a chunk that's changed, moved, dropped or added, a
file cut short or with anything after its last chunk, or a changed header all fail to decrypt.
"""

import os
from collections.abc import Iterator
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.crypto.errors import DecryptionError

MAGIC = b"BBK"
VERSION = 0x01
FINGERPRINT_BYTES = 16
SALT_BYTES = 16
HEADER_BYTES = len(MAGIC) + 1 + FINGERPRINT_BYTES + SALT_BYTES
CHUNK_BYTES = 1024 * 1024
TAG_BYTES = 16
_FILE_KEY_INFO = b"budget-buddy/v1/backup-file"

NOT_A_BACKUP = "That file isn't a Budget Buddy backup."
DAMAGED = (
    "That backup couldn't be opened: it was changed or damaged, or it's cut short. Try another "
    "copy of it."
)


def _file_key(backup_key: bytes, salt: bytes) -> AESGCM:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=_FILE_KEY_INFO)
    return AESGCM(hkdf.derive(backup_key))


def _nonce(number: int, last: bool) -> bytes:
    return number.to_bytes(11, "big") + (b"\x01" if last else b"\x00")


def read_header(source: BinaryIO) -> tuple[str, bytes, bytes]:
    """(key fingerprint as hex, salt, the header bytes) from the start of a backup."""
    header = source.read(HEADER_BYTES)
    if len(header) != HEADER_BYTES or header[:3] != MAGIC:
        raise DecryptionError(NOT_A_BACKUP)
    if header[3] != VERSION:
        raise DecryptionError(
            "That backup was made by a newer Budget Buddy. Update this one, then try again."
        )
    fingerprint = header[4 : 4 + FINGERPRINT_BYTES].hex()
    return fingerprint, header[4 + FINGERPRINT_BYTES :], header


class EncryptingWriter:
    """A write-only file object: what's written goes to ``target`` encrypted. Call ``close()``
    at the end, which writes the last chunk; without it the file can't be opened."""

    def __init__(self, target: BinaryIO, backup_key: bytes, fingerprint: str) -> None:
        salt = os.urandom(SALT_BYTES)
        self._header = MAGIC + bytes([VERSION]) + bytes.fromhex(fingerprint) + salt
        if len(self._header) != HEADER_BYTES:
            raise ValueError("A key fingerprint is 16 bytes.")
        self._aead = _file_key(backup_key, salt)
        self._target = target
        self._buffer = bytearray()
        self._number = 0
        self.closed = False
        target.write(self._header)

    def write(self, data: bytes) -> int:
        self._buffer += data
        while len(self._buffer) > CHUNK_BYTES:  # keep at least one byte back for the last chunk
            self._seal(bytes(self._buffer[:CHUNK_BYTES]), last=False)
            del self._buffer[:CHUNK_BYTES]
        return len(data)

    def close(self) -> None:
        if not self.closed:
            self._seal(bytes(self._buffer), last=True)
            self._buffer.clear()
            self.closed = True

    def _seal(self, chunk: bytes, last: bool) -> None:
        nonce = _nonce(self._number, last)
        self._target.write(self._aead.encrypt(nonce, chunk, self._header))
        self._number += 1


def decrypted_chunks(
    source: BinaryIO, backup_key: bytes, salt: bytes, header: bytes
) -> Iterator[bytes]:
    """The contents after :func:`read_header`, a chunk at a time. Raises DecryptionError if
    anything about the file isn't exactly as it was written."""
    aead = _file_key(backup_key, salt)
    size = CHUNK_BYTES + TAG_BYTES
    current, number = source.read(size), 0
    while True:
        following = source.read(size) if len(current) == size else b""
        last = not following
        try:
            yield aead.decrypt(_nonce(number, last), current, header)
        except InvalidTag as exc:
            raise DecryptionError(DAMAGED) from exc
        if last:
            return
        current, number = following, number + 1


class DecryptingReader:
    """A read-only file object over :func:`decrypted_chunks`, for ``tarfile`` streaming."""

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks
        self._buffer = bytearray()
        self._done = False

    def read(self, size: int = -1) -> bytes:
        while not self._done and (size < 0 or len(self._buffer) < size):
            chunk = next(self._chunks, None)
            if chunk is None:
                self._done = True
            else:
                self._buffer += chunk
        size = len(self._buffer) if size < 0 else min(size, len(self._buffer))
        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    def drain(self) -> None:
        """Read (and so check) everything that's left, including the last chunk's tag."""
        while self.read(CHUNK_BYTES):
            pass
