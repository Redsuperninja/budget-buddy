"""Checking receipt photos and removing hidden details (location, camera) before they're saved.

No image library is needed: the file type is read from its first bytes (never from the file name
or the ``Content-Type`` the browser sends), and JPEG and PNG files are walked piece by piece,
keeping only what's needed to show the picture. The image itself is never decoded here.

HEIC photos are walked box by box: the bytes of the Exif and XMP items are overwritten with zeros
and those items are renamed, so the file keeps its size and every offset stays valid (#34).
JPEG keeps a tiny rebuilt Exif block holding only the rotation, so sideways photos still show upright.

Used by the computer-side receipts API and meant for phone uploads over sync (#15) too.
"""

import zlib
from dataclasses import dataclass

MAX_IMAGE_BYTES = 3 * 1024 * 1024  # sync contract §6.1


@dataclass(frozen=True)
class ImageKind:
    mime: str
    extension: str


JPEG = ImageKind("image/jpeg", "jpg")
PNG = ImageKind("image/png", "png")
HEIC = ImageKind("image/heic", "heic")

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_HEIC_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx"}
_HEIF_GENERIC_BRANDS = {b"mif1", b"msf1"}  # also used by AVIF, so check the other brands

# PNG pieces that hold the picture or how to show its colours. Everything else (text, dates,
# EXIF, unknown extras) is dropped.
_PNG_KEEP = {
    b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"cHRM", b"gAMA", b"iCCP", b"sBIT", b"sRGB",
    b"bKGD", b"pHYs",
}  # fmt: skip
# JPEG "start of frame" markers (C4, C8 and CC are other things).
_JPEG_SOF = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
_JPEG_SOS, _JPEG_EOI = 0xDA, 0xD9


class ImageRejected(ValueError):
    """The upload can't be saved. ``reason`` matches the sync contract's ``ReceiptResult``."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _invalid() -> ImageRejected:
    return ImageRejected(
        "image_invalid",
        "That file isn't a photo Budget Buddy can read. Please use a JPEG, PNG or HEIC picture.",
    )


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) from a JPEG's frame header, reading only the headers, never the picture."""
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker == 0xFF:  # fill byte
            i += 1
            continue
        if marker in (0x01, _JPEG_EOI, _JPEG_SOS) or 0xD0 <= marker <= 0xD8:
            return None  # no frame header before the picture data starts
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        if length < 2:
            return None
        if marker in _JPEG_SOF:
            if i + 9 > len(data):
                return None
            height = int.from_bytes(data[i + 5 : i + 7], "big")
            width = int.from_bytes(data[i + 7 : i + 9], "big")
            return (width, height) if width and height else None
        i += 2 + length
    return None


def too_large() -> ImageRejected:
    return ImageRejected(
        "image_too_large",
        f"That photo is too big. The limit is {MAX_IMAGE_BYTES // 1_048_576} MB; try a smaller "
        "or lower-quality picture.",
    )


def detect_kind(data: bytes) -> ImageKind | None:
    """What kind of image ``data`` is, from its first bytes only. ``None`` if not one we take."""
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG
    if data.startswith(PNG_SIGNATURE):
        return PNG
    if len(data) >= 16 and data[4:8] == b"ftyp":
        size = int.from_bytes(data[0:4], "big")
        major = data[8:12]
        brands = {data[i : i + 4] for i in range(16, min(size, len(data), 64), 4)}
        if major in _HEIC_BRANDS or (major in _HEIF_GENERIC_BRANDS and brands & _HEIC_BRANDS):
            return HEIC
    return None


def clean_image(data: bytes) -> tuple[bytes, ImageKind]:
    """Check an uploaded photo and strip its metadata. Raises :class:`ImageRejected`."""
    if len(data) > MAX_IMAGE_BYTES:
        raise too_large()
    kind = detect_kind(data)
    if kind is JPEG:
        return _strip_jpeg(data), kind
    if kind is PNG:
        return _strip_png(data), kind
    if kind is HEIC:
        return _strip_heic(data), kind
    raise _invalid()


def _keep_jpeg_segment(marker: int, payload: bytes) -> bool:
    if 0xE0 <= marker <= 0xEF:  # APP0-APP15: EXIF, GPS, XMP, maker notes, thumbnails...
        return (
            (marker == 0xE0 and payload.startswith(b"JFIF\x00"))
            or (marker == 0xE2 and payload.startswith(b"ICC_PROFILE\x00"))
            or (marker == 0xEE and payload.startswith(b"Adobe"))  # needed for CMYK colours
        )
    return marker != 0xFE  # FE = free-text comment


def _end_of_scan(data: bytes, i: int) -> int:
    """Index of the marker after a JPEG scan's compressed data (FF00 and FFD0-D7 are data)."""
    while True:
        i = data.find(b"\xff", i)
        if i < 0 or i + 1 >= len(data):
            raise _invalid()
        following = data[i + 1]
        if following == 0x00 or 0xD0 <= following <= 0xD7 or following == 0xFF:
            i += 1 if following == 0xFF else 2
            continue
        return i


def _jpeg_orientation(payload: bytes) -> int | None:
    """The rotation (2-8) from an Exif block's first directory, or ``None`` (missing, upright, odd)."""
    if not payload.startswith(b"Exif\x00\x00") or len(payload) < 22:
        return None
    tiff = payload[6:]
    order = {b"II": "little", b"MM": "big"}.get(tiff[:2])
    if order is None:
        return None
    ifd = int.from_bytes(tiff[4:8], order)
    if ifd + 2 > len(tiff):
        return None
    count = int.from_bytes(tiff[ifd : ifd + 2], order)
    for n in range(min(count, 256)):
        entry = tiff[ifd + 2 + 12 * n : ifd + 14 + 12 * n]
        if len(entry) < 12:
            return None
        if int.from_bytes(entry[0:2], order) == 0x0112:
            ok = int.from_bytes(entry[2:4], order) == 3 and int.from_bytes(entry[4:8], order) == 1
            value = int.from_bytes(entry[8:10], order)
            return value if ok and 2 <= value <= 8 else None
    return None


def _orientation_segment(value: int) -> bytes:
    """An Exif block holding nothing but the rotation (no location, camera or time)."""
    tiff = b"MM\x00*\x00\x00\x00\x08" + b"\x00\x01" + b"\x01\x12\x00\x03\x00\x00\x00\x01"
    tiff += value.to_bytes(2, "big") + b"\x00\x00" + b"\x00\x00\x00\x00"
    return b"\xff\xe1" + (len(tiff) + 8).to_bytes(2, "big") + b"Exif\x00\x00" + tiff


def _strip_jpeg(data: bytes) -> bytes:
    out = bytearray(b"\xff\xd8")
    i, seen_frame, insert_at, orientation = 2, False, 2, None
    while True:
        if i >= len(data) or data[i] != 0xFF:
            raise _invalid()
        while i < len(data) - 1 and data[i + 1] == 0xFF:  # optional fill bytes
            i += 1
        if i + 4 > len(data):
            raise _invalid()
        marker = data[i + 1]
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        end = i + 2 + length
        if marker in (0x01, _JPEG_EOI) or 0xD0 <= marker <= 0xD8 or length < 2 or end > len(data):
            raise _invalid()
        payload = data[i + 4 : end]
        if marker == 0xE1 and orientation is None:
            orientation = _jpeg_orientation(payload)
        if _keep_jpeg_segment(marker, payload):
            out += data[i:end]
            if marker == 0xE0 and len(out) == 2 + (end - i):  # JFIF must stay first
                insert_at = len(out)
        seen_frame |= marker in _JPEG_SOF
        i = end
        if marker == _JPEG_SOS:
            if not seen_frame:
                raise _invalid()
            i = _end_of_scan(data, i)
            out += data[end:i]
            if data[i + 1] == _JPEG_EOI:
                # Anything after the end (extra pictures, maker trailers) is dropped.
                if orientation:
                    out[insert_at:insert_at] = _orientation_segment(orientation)
                return bytes(out + b"\xff\xd9")


def _strip_png(data: bytes) -> bytes:
    out = bytearray(PNG_SIGNATURE)
    i, first, seen_data = len(PNG_SIGNATURE), True, False
    while True:
        if i + 12 > len(data):
            raise _invalid()
        length = int.from_bytes(data[i : i + 4], "big")
        chunk_type = data[i + 4 : i + 8]
        end = i + 12 + length
        if end > len(data) or (first and chunk_type != b"IHDR"):
            raise _invalid()
        if zlib.crc32(data[i + 4 : end - 4]) != int.from_bytes(data[end - 4 : end], "big"):
            raise _invalid()
        if chunk_type in _PNG_KEEP:
            out += data[i:end]
        seen_data |= chunk_type == b"IDAT"
        first, i = False, end
        if chunk_type == b"IEND":
            if not seen_data:
                raise _invalid()
            return bytes(out)  # anything after the end is dropped


# --- HEIC (ISO base media file format) ---------------------------------------------------------


def _boxes(data: bytes | memoryview, start: int, end: int):
    """Yield ``(type, payload_start, box_end)`` for the boxes between ``start`` and ``end``."""
    i = start
    while i < end:
        if i + 8 > end:
            raise _invalid()
        size, kind = int.from_bytes(data[i : i + 4], "big"), bytes(data[i + 4 : i + 8])
        header = 8
        if size == 1:
            if i + 16 > end:
                raise _invalid()
            size, header = int.from_bytes(data[i + 8 : i + 16], "big"), 16
        elif size == 0:
            size = end - i
        if size < header or i + size > end:
            raise _invalid()
        yield kind, i + header, i + size
        i += size


def _heic_secret_items(data: bytes, iinf: tuple[int, int]) -> tuple[dict[int, int], list[int]]:
    """Item ids holding Exif or XMP, and where each one's 4-byte type sits in the file."""
    start, end = iinf
    version = data[start]
    pos = start + 4 + (2 if version == 0 else 4)  # skip version/flags and the entry count
    ids: dict[int, int] = {}
    for kind, p, e in _boxes(data, pos, end):
        if kind != b"infe" or e - p < 12 or data[p] < 2:
            continue
        v = data[p]
        width = 2 if v == 2 else 4
        item_id = int.from_bytes(data[p + 4 : p + 4 + width], "big")
        type_at = p + 4 + width + 2
        item_type = data[type_at : type_at + 4]
        rest = data[type_at + 4 : e].lower()
        if item_type == b"Exif" or (
            item_type == b"mime" and (b"xmp" in rest or b"rdf+xml" in rest or b"xml" in rest)
        ):
            ids[item_id] = type_at
    return ids, list(ids.values())


def _heic_extents(data: bytes, iloc: tuple[int, int], idat: int | None, wanted: dict[int, int]):
    """File ranges ``(start, end)`` holding the data of the ``wanted`` items."""
    p, end = iloc
    version = data[p]
    p += 4
    offset_size, length_size = data[p] >> 4, data[p] & 15
    base_size, index_size = data[p + 1] >> 4, (data[p + 1] & 15) if version in (1, 2) else 0
    p += 2
    count = int.from_bytes(data[p : p + (4 if version == 2 else 2)], "big")
    p += 4 if version == 2 else 2
    if length_size == 0 or version > 2:
        raise _invalid()

    def take(n: int) -> int:
        nonlocal p
        if p + n > end:
            raise _invalid()
        value = int.from_bytes(data[p : p + n], "big")
        p += n
        return value

    ranges = []
    for _ in range(count):
        item_id = take(4 if version == 2 else 2)
        method = take(2) & 15 if version in (1, 2) else 0
        take(2)  # data reference index
        base = take(base_size)
        for _ in range(take(2)):
            if index_size:
                take(index_size)
            offset, length = take(offset_size), take(length_size)
            if item_id not in wanted:
                continue
            if method == 0:
                a = base + offset
            elif method == 1 and idat is not None:
                a = idat + base + offset
            else:
                raise _invalid()
            if a + length > len(data):
                raise _invalid()
            ranges.append((a, a + length))
    return ranges


def _strip_heic(data: bytes) -> bytes:
    """Blank the Exif and XMP items in place (same size, so every offset in the file stays valid)."""
    meta = iinf = iloc = idat = None
    for kind, p, e in _boxes(data, 0, len(data)):
        if kind == b"meta":
            meta = (p + 4, e)  # a "full box": 4 bytes of version/flags first
    if meta is None or meta[0] > meta[1]:
        raise _invalid()
    for kind, p, e in _boxes(data, *meta):
        if kind == b"iinf":
            iinf = (p, e)
        elif kind == b"iloc":
            iloc = (p, e)
        elif kind == b"idat":
            idat = p
    if iinf is None or iloc is None:
        raise _invalid()
    try:
        ids, type_positions = _heic_secret_items(data, iinf)
        ranges = _heic_extents(data, iloc, idat, ids) if ids else []
    except IndexError:
        raise _invalid() from None
    out = bytearray(data)
    for a, b in ranges:
        out[a:b] = bytes(b - a)
    for at in type_positions:
        out[at : at + 4] = b"free"  # readers skip item types they don't know
    return bytes(out)
