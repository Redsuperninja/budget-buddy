"""POST /api/sync/receipts: a phone uploads queued receipts (sync contract section 6).

Fake data and hand-built fake JPEGs only.
"""

import struct
import uuid

import fake_images as img
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from sync_helpers import Phone, pair_phone

from app.crypto.b64url import b64u_encode
from app.models import Receipt
from app.services.receipt_images import MAX_IMAGE_BYTES, jpeg_size

PATH = "/api/sync/receipts"


@pytest.fixture
def phone(make_client) -> Phone:
    return pair_phone(make_client())


def cid() -> str:
    return str(uuid.uuid4())


def upload(**overrides) -> dict:
    item = {
        "client_id": cid(),
        "captured_at": "2026-09-20T12:14:03-05:00",
        "merchant": "Fake Corner Pharmacy",
        "total_cents": 2399,
        "category_id": None,
        "note": "Allergy meds",
        "tax_deductible": True,
        "deduction_kind": "medical",
        "image": {
            "mime": "image/jpeg",
            "width": 16,
            "height": 16,
            "data": b64u_encode(img.jpeg()),
        },
    }
    return item | overrides


def image_of(data: bytes) -> dict:
    return {"mime": "image/jpeg", "width": 1, "height": 1, "data": b64u_encode(data)}


def jpeg_sized(width: int, height: int) -> bytes:
    sof = img.segment(0xC0, b"\x08" + struct.pack(">HH", height, width) + b"\x01\x01\x11\x00")
    return b"\xff\xd8" + img.JFIF + img.DQT + sof + img.DHT + img.SOS + img.SCAN + b"\xff\xd9"


def send(phone: Phone, *items: dict) -> list[dict]:
    return phone.ok(PATH, {"receipts": list(items)})["results"]


def rows(phone: Phone) -> list[Receipt]:
    with Session(phone.dashboard.app.state.engine) as session:
        return list(session.scalars(select(Receipt).order_by(Receipt.id)))


def test_accepted_receipt_is_saved_with_an_encrypted_photo(phone):
    item = upload()
    (result,) = send(phone, item)
    assert result == {"client_id": item["client_id"], "status": "accepted", "receipt_id": 1}
    (row,) = rows(phone)
    assert (row.merchant, row.total_cents, row.tax_deductible) == (
        "Fake Corner Pharmacy",
        2399,
        True,
    )
    assert str(row.date) == "2026-09-20"  # the day on the phone, not converted to UTC
    assert (row.notes, row.deduction_kind, row.client_id) == (
        "Allergy meds",
        "medical",
        item["client_id"],
    )
    # The dashboard can see the photo, with its hidden details removed, and the file on disk
    # is encrypted.
    shown = phone.dashboard.get(f"/api/local/receipts/{result['receipt_id']}/image")
    assert shown.status_code == 200 and shown.content == img.clean_jpeg()
    files = list(phone.dashboard.app.state.receipt_store.directory.iterdir())
    assert len(files) == 1 and img.clean_jpeg() not in files[0].read_bytes()


def test_hidden_details_in_the_photo_are_stripped(phone):
    (result,) = send(phone, upload())
    shown = phone.dashboard.get(f"/api/local/receipts/{result['receipt_id']}/image").content
    assert b"FAKE-LOCATION" not in shown and b"FAKE-XMP" not in shown


def test_same_client_id_is_a_duplicate_and_first_upload_wins(phone):
    first = upload()
    send(phone, first)
    (again,) = send(phone, first | {"merchant": "Different Shop", "total_cents": 1})
    assert again == {"client_id": first["client_id"], "status": "duplicate", "receipt_id": 1}
    (row,) = rows(phone)
    assert row.merchant == "Fake Corner Pharmacy"
    assert len(list(phone.dashboard.app.state.receipt_store.directory.iterdir())) == 1


def test_duplicate_inside_one_batch(phone):
    item = upload()
    results = send(phone, item, item)
    assert [r["status"] for r in results] == ["accepted", "duplicate"]
    assert results[0]["receipt_id"] == results[1]["receipt_id"]


def test_results_come_back_in_order_and_one_bad_item_does_not_fail_the_rest(phone):
    good, bad = upload(), upload(image=image_of(img.png()))
    results = send(phone, good, bad, upload())
    assert [r["client_id"] for r in results[:2]] == [good["client_id"], bad["client_id"]]
    assert [r["status"] for r in results] == ["accepted", "rejected", "accepted"]
    assert results[1]["reason"] == "image_invalid" and results[1]["message"]
    assert len(rows(phone)) == 2


def test_unknown_category_is_dropped_with_a_warning(phone):
    (result,) = send(phone, upload(category_id=99999))
    assert result["status"] == "accepted" and result["warnings"] == ["unknown_category"]
    assert rows(phone)[0].category_id is None


def test_known_category_is_kept(phone):
    category = phone.dashboard.get("/api/local/categories").json()[0]["id"]
    (result,) = send(phone, upload(category_id=category))
    assert "warnings" not in result and rows(phone)[0].category_id == category


def test_optional_fields_can_be_left_out(phone):
    item = upload()
    for field in ("merchant", "total_cents", "category_id", "note", "deduction_kind"):
        del item[field]
    item["tax_deductible"] = False
    (result,) = send(phone, item)
    assert result["status"] == "accepted"
    (row,) = rows(phone)
    assert (row.merchant, row.total_cents, row.notes) == ("Receipt from phone", 0, None)
    assert row.tax_deductible is False and row.deduction_kind is None


def test_tax_deductible_without_a_kind_means_other(phone):
    send(phone, upload(deduction_kind=None))
    assert rows(phone)[0].deduction_kind == "other"


@pytest.mark.parametrize(
    "change",
    [
        {"captured_at": "2026-09-20T12:14:03"},  # no offset
        {"captured_at": "yesterday"},
        {"captured_at": None},
        {"total_cents": -1},
        {"total_cents": 12.5},
        {"total_cents": True},
        {"merchant": "x" * 101},
        {"merchant": 5},
        {"note": "x" * 501},
        {"category_id": 0},
        {"category_id": "1"},
        {"tax_deductible": "yes"},
        {"deduction_kind": "gift"},
    ],
)
def test_bad_fields_reject_only_that_item(phone, change):
    (result,) = send(phone, upload(**change))
    assert result["status"] == "rejected" and result["reason"] == "invalid_field"
    assert rows(phone) == []
    assert not list(phone.dashboard.app.state.receipt_store.directory.glob("*"))


@pytest.mark.parametrize(
    ("image", "reason"),
    [
        (image_of(img.png()), "image_invalid"),  # only JPEG is allowed over sync
        (image_of(b"hello world, not a photo"), "image_invalid"),
        (image_of(b"\xff\xd8\xff\xe0 broken"), "image_invalid"),
        (image_of(jpeg_sized(4097, 100)), "image_too_large"),
        (image_of(jpeg_sized(4096, 4096)), "image_too_large"),  # 16.7 megapixels
        (image_of(img.jpeg(trailer=bytes(MAX_IMAGE_BYTES))), "image_too_large"),
        (
            {"mime": "image/png", "width": 1, "height": 1, "data": b64u_encode(img.jpeg())},
            "image_invalid",
        ),
        ({"mime": "image/jpeg", "data": "not base64 !!"}, "image_invalid"),
        ({"mime": "image/jpeg", "data": "AAAAA"}, "image_invalid"),
        ({"mime": "image/jpeg", "data": 5}, "image_invalid"),
        ({"mime": "image/jpeg", "data": "A" * (4 * 1024 * 1024 + 8)}, "image_too_large"),
        ("not an object", "image_invalid"),
    ],
)
def test_bad_photos_are_rejected_per_item(phone, image, reason):
    (result,) = send(phone, upload(image=image))
    assert result["status"] == "rejected" and result["reason"] == reason
    assert rows(phone) == []


def test_megapixel_limit_is_16_million_pixels(phone):
    (result,) = send(phone, upload(image=image_of(jpeg_sized(4096, 4000))))  # 16.4 MP
    assert result["reason"] == "image_too_large"
    (ok,) = send(phone, upload(image=image_of(jpeg_sized(4000, 4000))))  # exactly 16 MP
    assert ok["status"] == "accepted"


def test_jpeg_size_reads_only_the_header():
    assert jpeg_size(img.jpeg()) == (16, 16)
    assert jpeg_size(jpeg_sized(1200, 1600)) == (1200, 1600)
    assert jpeg_size(b"\xff\xd8\xff") is None
    assert jpeg_size(b"\xff\xd8" + img.JFIF) is None


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"receipts": []},
        {"receipts": "x"},
        {"receipts": [upload() for _ in range(6)]},
        {"receipts": ["nope"]},
        {"receipts": [upload(client_id="not-a-uuid")]},
        {"receipts": [upload(client_id=str(uuid.uuid4()).upper())]},
        {"receipts": [upload(client_id="3f1c9a0e-8b7d-1c2a-9e51-6d0b7a2f4c18")]},  # not v4
        {"receipts": [{k: v for k, v in upload().items() if k != "client_id"}]},
    ],
)
def test_malformed_batches_are_an_encrypted_bad_request(phone, data):
    response, nonce = phone.call(PATH, data)
    assert response.status_code == 400
    assert phone.open(response, nonce)["error"]["code"] == "bad_request"
    assert rows(phone) == []


def test_five_receipts_in_a_batch_is_fine(phone):
    results = send(phone, *[upload() for _ in range(5)])
    assert [r["status"] for r in results] == ["accepted"] * 5


def test_body_over_12_mib_is_413_and_a_smaller_one_is_not(phone):
    response, _ = phone.call(PATH, body=b"x" * (12 * 1024 * 1024 + 1))
    assert response.status_code == 413 and response.json()["error"]["code"] == "too_large"
    big = image_of(img.jpeg(trailer=bytes(MAX_IMAGE_BYTES - 2000)))
    results = send(phone, upload(image=big), upload(image=big))
    assert [r["status"] for r in results] == ["accepted"] * 2  # about 8 MiB of text is fine


def test_nothing_about_a_receipt_reaches_the_logs(phone, caplog):
    caplog.set_level("DEBUG")
    send(phone, upload(merchant="Fake Secret Merchant", note="Fake Secret Note"))
    send(phone, upload(image=image_of(b"nope")))
    text = caplog.text
    assert "Fake Secret" not in text and "2399" not in text
