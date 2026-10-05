"""Checking receipt photos and removing hidden details (location, camera) before they're saved.

No image library is needed: the file type is read from its first bytes (never from the file name
or the ``Content-Type`` the browser sends), and JPEG and PNG files are walked piece by piece,
keeping only what's needed to show the picture. The image itself is never decoded here.

HEIC photos are checked but saved as they are: their metadata can't be removed without a heavy
library, so they may still hold the photo's location (see the receipts docs).

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
        return data, kind
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


def _strip_jpeg(data: bytes) -> bytes:
    out = bytearray(b"\xff\xd8")
    i, seen_frame = 2, False
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
        if _keep_jpeg_segment(marker, data[i + 4 : end]):
            out += data[i:end]
        seen_frame |= marker in _JPEG_SOF
        i = end
        if marker == _JPEG_SOS:
            if not seen_frame:
                raise _invalid()
            i = _end_of_scan(data, i)
            out += data[end:i]
            if data[i + 1] == _JPEG_EOI:
                # Anything after the end (extra pictures, maker trailers) is dropped.
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
