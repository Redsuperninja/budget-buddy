"""Tiny hand-built image files for receipt tests. No real photos, no image library needed."""

import struct
import zlib


def segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


JFIF = segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
EXIF = segment(0xE1, b"Exif\x00\x00GPSLatitude 51.5 FAKE-LOCATION Camera FakePhone")
XMP = segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>FAKE-XMP</x:xmpmeta>")
COMMENT = segment(0xFE, b"FAKE-COMMENT")
ICC = segment(0xE2, b"ICC_PROFILE\x00\x01\x01fake-icc")
DQT = segment(0xDB, b"\x00" + bytes(range(64)))
SOF0 = segment(0xC0, b"\x08\x00\x10\x00\x10\x01\x01\x11\x00")
DHT = segment(0xC4, b"\x00" + bytes(16))
SOS = segment(0xDA, b"\x01\x01\x00\x00\x3f\x00")
# Compressed data with a stuffed FF00 and a restart marker, which are part of the scan.
SCAN = b"\x12\x34\xff\x00\x56\xff\xd0\x78\x9a"


def jpeg(*, with_metadata: bool = True, trailer: bytes = b"") -> bytes:
    meta = EXIF + XMP + COMMENT if with_metadata else b""
    return b"\xff\xd8" + JFIF + meta + ICC + DQT + SOF0 + DHT + SOS + SCAN + b"\xff\xd9" + trailer


def clean_jpeg() -> bytes:
    """What :func:`jpeg` should look like after its metadata is stripped."""
    return jpeg(with_metadata=False)


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
IHDR = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
IDAT = chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
IEND = chunk(b"IEND", b"")


def png(*, with_metadata: bool = True, trailer: bytes = b"") -> bytes:
    meta = (
        chunk(b"tEXt", b"Comment\x00FAKE-LOCATION") + chunk(b"eXIf", b"MM\x00*FAKE-EXIF")
        if with_metadata
        else b""
    )
    return PNG_SIGNATURE + IHDR + meta + IDAT + IEND + trailer


def heic() -> bytes:
    ftyp = b"ftyp" + b"heic" + b"\x00\x00\x00\x00" + b"mif1heic"
    return struct.pack(">I", len(ftyp) + 4) + ftyp + b"\x00\x00\x00\x08free" + b"fake-heic"
