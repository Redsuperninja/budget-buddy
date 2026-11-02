"""Receipt photo checks: type from magic bytes, size cap, metadata stripping. Fake images only."""

import struct

import fake_images as img
import pytest

from app.services.devices.receipt_images import (
    HEIC,
    JPEG,
    MAX_IMAGE_BYTES,
    PNG,
    ImageRejected,
    clean_image,
    detect_kind,
)


def test_detects_kind_from_first_bytes_only():
    assert detect_kind(img.jpeg()) is JPEG
    assert detect_kind(img.png()) is PNG
    assert detect_kind(img.heic()) is HEIC
    assert detect_kind(b"GIF89a....") is None
    assert detect_kind(b"<svg xmlns='http://www.w3.org/2000/svg'/>") is None
    assert detect_kind(b"") is None


def ftyp(major: bytes, *compatible: bytes) -> bytes:
    body = b"ftyp" + major + b"\x00\x00\x00\x00" + b"".join(compatible)
    return struct.pack(">I", len(body) + 4) + body + b"rest"


def test_heif_container_must_be_heic_not_avif():
    assert detect_kind(ftyp(b"mif1", b"mif1", b"heic")) is HEIC
    assert detect_kind(ftyp(b"avif", b"mif1", b"avif")) is None
    assert detect_kind(ftyp(b"mif1", b"mif1", b"avif")) is None
    assert detect_kind(ftyp(b"isom", b"mp41")) is None  # an MP4 video


def test_jpeg_metadata_and_trailer_are_removed():
    cleaned, kind = clean_image(img.jpeg(trailer=b"FAKE-TRAILER-WITH-EXIF"))
    assert kind is JPEG
    assert cleaned == img.clean_jpeg()
    for secret in (b"FAKE-LOCATION", b"Exif", b"FAKE-XMP", b"FAKE-COMMENT", b"FAKE-TRAILER"):
        assert secret not in cleaned
    assert img.ICC in cleaned and img.SCAN in cleaned  # colours and the picture itself stay


def test_jpeg_with_several_scans_keeps_them_all():
    # Progressive JPEGs have a table and another scan between the first scan and the end.
    data = img.jpeg(with_metadata=False)
    two_scans = data[:-2] + img.DHT + img.SOS + img.SCAN + b"\xff\xd9"
    assert clean_image(two_scans)[0] == two_scans


@pytest.mark.parametrize(
    "data",
    [
        img.jpeg()[:-2],  # cut off before the end
        img.jpeg()[:30],
        b"\xff\xd8\xff",
        b"\xff\xd8" + img.JFIF + img.SOS + img.SCAN + b"\xff\xd9",  # no frame header
        b"\xff\xd8" + img.JFIF + b"\xff\xe1\x00\x01",  # impossible segment length
        b"\xff\xd8" + img.JFIF + b"\xff\xe1\xff\xff" + b"short",  # length past the end
    ],
)
def test_broken_jpeg_is_rejected(data):
    with pytest.raises(ImageRejected) as caught:
        clean_image(data)
    assert caught.value.reason == "image_invalid"


def test_png_metadata_and_trailer_are_removed():
    cleaned, kind = clean_image(img.png(trailer=b"FAKE-TRAILER"))
    assert kind is PNG
    assert cleaned == img.png(with_metadata=False)
    assert b"FAKE" not in cleaned and b"tEXt" not in cleaned and b"eXIf" not in cleaned


@pytest.mark.parametrize(
    "data",
    [
        img.png()[:-4],  # cut off
        img.PNG_SIGNATURE + img.IDAT + img.IEND,  # doesn't start with the header chunk
        img.PNG_SIGNATURE + img.IHDR + img.IEND,  # no picture data
        img.png().replace(b"FAKE-LOCATION", b"FAKE-LOCATIOM"),  # checksum no longer matches
    ],
)
def test_broken_png_is_rejected(data):
    with pytest.raises(ImageRejected) as caught:
        clean_image(data)
    assert caught.value.reason == "image_invalid"


def test_heic_exif_and_xmp_are_blanked_in_place():
    original = img.heic()
    cleaned, kind = clean_image(original)
    assert kind is HEIC
    assert len(cleaned) == len(original)  # same size, so every offset in the file stays valid
    assert img.PICTURE in cleaned
    for secret in (b"FAKE-LOCATION", b"GPSLatitude", b"FAKE-XMP-LOCATION", b"Exif"):
        assert secret not in cleaned


def test_heic_without_metadata_is_unchanged():
    plain = img.heic(with_metadata=False)
    assert clean_image(plain) == (plain, HEIC)


@pytest.mark.parametrize("cut", [20, 40, 70, 100])
def test_broken_heic_is_rejected(cut):
    with pytest.raises(ImageRejected) as caught:
        clean_image(img.heic()[:cut])
    assert caught.value.reason == "image_invalid"


@pytest.mark.parametrize(
    "crafted",
    [
        img.heic(second_meta=True),  # readers use the first meta; a scanner would use the last
        img.heic(extra_top=img._box(b"moov", b"\x00" * 8)),  # video box that can hold a location
        img.heic(extra_top=img._box(b"uuid", b"\x00" * 24)),
        img.heic(exif_extents=500),  # many tiny writes: a slow upload
        img.heic(exif_extent_length=0),  # "the whole item": we couldn't tell what to blank
        img.heic(duplicate_id=True),  # two items with one id: which one is the Exif?
    ],
    ids=["second-meta", "moov", "uuid", "many-extents", "zero-length-extent", "duplicate-id"],
)
def test_crafted_heic_is_rejected(crafted):
    with pytest.raises(ImageRejected) as caught:
        clean_image(crafted)
    assert caught.value.reason == "image_invalid"


def test_heic_xml_box_is_blanked():
    cleaned, _ = clean_image(img.heic(xml_box=True))
    assert b"FAKE-XML-LOCATION" not in cleaned


def test_jpeg_extras_are_dropped():
    thumb = img.segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x01\x01" + b"FAKE-THUMB-LOCATION")
    extra = img.segment(0xF5, b"FAKE-JPGN-LOCATION")
    data = b"\xff\xd8" + thumb + extra + img.DQT + img.SOF0 + img.DHT + img.SOS + img.SCAN + b"\xff\xd9"
    cleaned, _ = clean_image(data)
    assert b"FAKE-THUMB-LOCATION" not in cleaned and b"FAKE-JPGN-LOCATION" not in cleaned
    assert cleaned.startswith(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00")
    assert cleaned[6 + 12 : 6 + 14] == b"\x00\x00"  # thumbnail size reset to none


def test_heic_without_item_index_is_rejected():
    ftyp = img.heic()[:24]
    with pytest.raises(ImageRejected):
        clean_image(ftyp + img._box(b"mdat", b"x"))


@pytest.mark.parametrize("little", [False, True])
@pytest.mark.parametrize("value", [2, 3, 6, 8])
def test_jpeg_keeps_only_the_rotation(value, little):
    cleaned, _ = clean_image(img.rotated_jpeg(value, little=little))
    assert b"FAKE-LOCATION" not in cleaned and b"FakePhone" not in cleaned
    assert cleaned.startswith(b"\xff\xd8" + img.JFIF)  # JFIF stays first
    assert b"Exif\x00\x00MM\x00*" in cleaned
    assert cleaned.count(b"Exif") == 1
    tag = cleaned.index(b"\x01\x12\x00\x03\x00\x00\x00\x01")
    assert int.from_bytes(cleaned[tag + 8 : tag + 10], "big") == value


def test_upright_jpeg_gets_no_exif_block():
    cleaned, _ = clean_image(img.rotated_jpeg(1))
    assert b"Exif" not in cleaned
    assert cleaned == img.clean_jpeg().replace(img.ICC, b"")


def test_size_cap():
    big = img.jpeg(with_metadata=False)
    padding = b"\xff\xd8" + img.segment(0xE4, b"x" * 65_000) * 49  # ~3.04 MiB of APP4 segments
    with pytest.raises(ImageRejected) as caught:
        clean_image(padding + big[2:])
    assert caught.value.reason == "image_too_large"
    assert len(padding) > MAX_IMAGE_BYTES


@pytest.mark.parametrize("data", [b"", b"hello", b"%PDF-1.7 fake", b"MZ\x90\x00"])
def test_other_files_are_rejected(data):
    with pytest.raises(ImageRejected) as caught:
        clean_image(data)
    assert caught.value.reason == "image_invalid"
    assert "JPEG, PNG or HEIC" in caught.value.message
