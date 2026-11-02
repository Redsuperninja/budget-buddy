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


def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload) + 8) + kind + payload


def _infe(item_id: int, item_type: bytes, extra: bytes = b"") -> bytes:
    return _box(b"infe", b"\x02\x00\x00\x00" + struct.pack(">HH", item_id, 0) + item_type + b"\x00" + extra)


PICTURE = b"FAKE-HEIC-PICTURE"
HEIC_EXIF = b"\x00\x00\x00\x00Exif\x00\x00GPSLatitude 51.5 FAKE-LOCATION"
HEIC_XMP = b"<x:xmpmeta>FAKE-XMP-LOCATION</x:xmpmeta>"


def heic(
    *,
    with_metadata: bool = True,
    exif_extents: int = 1,
    exif_extent_length: int | None = None,
    extra_top: bytes = b"",
    second_meta: bool = False,
    xml_box: bool = False,
    duplicate_id: bool = False,
) -> bytes:
    """A tiny HEIC-shaped file: picture, Exif and XMP items located by iinf/iloc, data in mdat.

    The keyword arguments build the crafted variants the importer must refuse or clean.
    """
    ftyp = _box(b"ftyp", b"heic\x00\x00\x00\x00mif1heic")
    items = [(1, b"hvc1", b"", PICTURE)]
    if with_metadata:
        items += [(2, b"Exif", b"", HEIC_EXIF), (3, b"mime", b"application/rdf+xml\x00", HEIC_XMP)]
    infe_items = items + ([(2, b"hvc1", b"", b"")] if duplicate_id else [])
    infe = b"".join(_infe(i, t, x) for i, t, x, _ in infe_items)
    iinf = _box(b"iinf", b"\x00\x00\x00\x00" + struct.pack(">H", len(infe_items)) + infe)
    xml = _box(b"xml ", b"\x00\x00\x00\x00<x>FAKE-XML-LOCATION</x>") if xml_box else b""

    def meta(first_offset: int) -> bytes:
        loc, at = b"", first_offset
        for i, _, _, payload in items:
            n = exif_extents if i == 2 else 1
            length = len(payload) if exif_extent_length is None or i != 2 else exif_extent_length
            loc += struct.pack(">HHH", i, 0, n) + struct.pack(">II", at, length) * n
            at += len(payload)
        iloc = _box(b"iloc", b"\x00\x00\x00\x00\x44" + b"\x00" + struct.pack(">H", len(items)) + loc)
        inner = iinf + iloc + xml
        return _box(b"meta", b"\x00\x00\x00\x00" + inner)

    start = len(ftyp) + len(meta(0)) + 8  # the first byte inside mdat
    metas = meta(start) * (2 if second_meta else 1)
    return ftyp + metas + extra_top + _box(b"mdat", b"".join(payload for *_, payload in items))


def exif_orientation(value: int, *, little: bool = False) -> bytes:
    """An Exif block with a rotation plus a fake location, as a phone would write it."""
    order = "little" if little else "big"
    head = b"II*\x00" + (8).to_bytes(4, "little") if little else b"MM\x00*" + (8).to_bytes(4, "big")
    entries = [(0x010F, 2, b"FakePhone\x00"), (0x0112, 3, None)]
    body = len(entries).to_bytes(2, order)
    for tag, typ, text in entries:
        if text is None:
            body += tag.to_bytes(2, order) + typ.to_bytes(2, order) + (1).to_bytes(4, order)
            body += value.to_bytes(2, order) + b"\x00\x00"
        else:  # a value too long for the entry: kept elsewhere; here just a fake pointer
            body += tag.to_bytes(2, order) + typ.to_bytes(2, order) + len(text).to_bytes(4, order) + b"\x00\x00\x00\x00"
    return b"Exif\x00\x00" + head + body + b"\x00\x00\x00\x00" + b"FAKE-LOCATION"


def rotated_jpeg(value: int, *, little: bool = False) -> bytes:
    return b"\xff\xd8" + JFIF + segment(0xE1, exif_orientation(value, little=little)) + DQT + SOF0 + DHT + SOS + SCAN + b"\xff\xd9"
