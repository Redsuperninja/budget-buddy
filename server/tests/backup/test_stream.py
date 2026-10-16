"""The chunked encryption under backup files: anything changed, cut, moved or added fails."""

import io
import os

import pytest

from app.crypto.errors import DecryptionError
from app.crypto.stream import (
    CHUNK_BYTES,
    HEADER_BYTES,
    TAG_BYTES,
    DecryptingReader,
    EncryptingWriter,
    decrypted_chunks,
    read_header,
)

KEY = bytes(range(32))
FINGERPRINT = "ab" * 16


def encrypt(contents: bytes, pieces: int = 3) -> bytes:
    out = io.BytesIO()
    writer = EncryptingWriter(out, KEY, FINGERPRINT)
    step = max(1, len(contents) // pieces)
    for start in range(0, len(contents), step):
        writer.write(contents[start : start + step])
    writer.close()
    return out.getvalue()


def decrypt(blob: bytes, key: bytes = KEY) -> bytes:
    source = io.BytesIO(blob)
    _fingerprint, salt, header = read_header(source)
    reader = DecryptingReader(decrypted_chunks(source, key, salt, header))
    data = reader.read()
    reader.drain()
    return data


@pytest.mark.parametrize(
    "size",
    [0, 1, CHUNK_BYTES - 1, CHUNK_BYTES, CHUNK_BYTES + 1, 2 * CHUNK_BYTES, 2 * CHUNK_BYTES + 5],
)
def test_round_trip_at_every_chunk_edge(size):
    contents = os.urandom(size)
    blob = encrypt(contents)
    chunks = max(1, -(-size // CHUNK_BYTES))
    assert len(blob) == HEADER_BYTES + size + chunks * TAG_BYTES
    assert decrypt(blob) == contents


def test_the_header_says_which_key_made_it():
    assert read_header(io.BytesIO(encrypt(b"x")))[0] == FINGERPRINT


def test_each_file_gets_its_own_key():
    assert encrypt(b"same")[HEADER_BYTES:] != encrypt(b"same")[HEADER_BYTES:]


def test_a_wrong_key_fails():
    with pytest.raises(DecryptionError):
        decrypt(encrypt(b"money"), key=bytes(32))


TWO_CHUNKS = os.urandom(CHUNK_BYTES + 100)
CHUNK = CHUNK_BYTES + TAG_BYTES


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(lambda b: b[:-1], id="last byte cut"),
        pytest.param(lambda b: b[: HEADER_BYTES + CHUNK], id="last chunk dropped"),
        pytest.param(lambda b: b + b"x", id="something added"),
        pytest.param(lambda b: b + b[HEADER_BYTES : HEADER_BYTES + CHUNK], id="chunk repeated"),
        pytest.param(
            lambda b: (
                b[:HEADER_BYTES]
                + b[HEADER_BYTES + CHUNK :]
                + b[HEADER_BYTES : HEADER_BYTES + CHUNK]
            ),
            id="chunks swapped",
        ),
        pytest.param(lambda b: b[:10] + bytes([b[10] ^ 1]) + b[11:], id="header changed"),
        pytest.param(lambda b: b[:-50] + bytes([b[-50] ^ 1]) + b[-49:], id="contents changed"),
    ],
)
def test_any_change_fails(tamper):
    with pytest.raises(DecryptionError):
        decrypt(tamper(encrypt(TWO_CHUNKS)))


def test_not_a_backup():
    with pytest.raises(DecryptionError, match="isn't a Budget Buddy backup"):
        read_header(io.BytesIO(b"PK\x03\x04" + bytes(40)))


def test_a_newer_format_says_so():
    blob = bytearray(encrypt(b""))
    blob[3] = 2
    with pytest.raises(DecryptionError, match="newer Budget Buddy"):
        read_header(io.BytesIO(bytes(blob)))
