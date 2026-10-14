"""Receipts API: details CRUD, encrypted photo upload/download, file clean-up. Fake data only."""

import logging
import os
import time

import fake_images as img
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Category
from app.services.devices import receipts as service
from app.services.devices.receipt_images import MAX_IMAGE_BYTES

URL = "/api/local/receipts"
MERCHANT = "Fake Corner Pharmacy"


@pytest.fixture
def make_receipt(client):
    def make(**overrides) -> dict:
        body = {"date": "2026-09-30", "merchant": MERCHANT, "total_cents": 2_399, **overrides}
        response = client.post(URL, json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return make


def store(client):
    return client.app.state.receipt_store


def stored_files(client) -> list[str]:
    directory = store(client).directory
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []


def upload(client, receipt_id, data, **headers):
    return client.put(f"{URL}/{receipt_id}/image", content=data, headers=headers)


def groceries(client) -> int:
    with SessionLocal(bind=client.app.state.engine) as session:
        return session.scalar(select(Category.id).where(Category.name == "Groceries"))


def test_receipt_details_crud(client, make_receipt, make_account, add_txn):
    txn = add_txn(make_account()["id"], -2_399)
    created = make_receipt(category_id=groceries(client), transaction_id=txn["id"], notes="fake")
    assert created["total_cents"] == 2_399
    assert (created["has_image"], created["tax_deductible"]) == (False, False)
    rid = created["id"]

    assert client.get(f"{URL}/{rid}").json()["notes"] == "fake"
    response = client.patch(
        f"{URL}/{rid}", json={"merchant": "Fake Grocer", "category_id": None, "total_cents": 0}
    )
    assert response.status_code == 200, response.text
    assert (response.json()["merchant"], response.json()["category_id"]) == ("Fake Grocer", None)
    assert response.json()["transaction_id"] == txn["id"]

    page = client.get(URL).json()
    assert (page["total"], page["items"][0]["id"]) == (1, rid)

    # Deleting the bank transaction just unlinks the receipt.
    assert client.delete(f"/api/local/transactions/{txn['id']}").status_code == 204
    assert client.get(f"{URL}/{rid}").json()["transaction_id"] is None

    assert client.delete(f"{URL}/{rid}").status_code == 204
    assert client.get(f"{URL}/{rid}").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"total_cents": -1},
        {"total_cents": 12.5},
        {"total_cents": "1250"},
        {"merchant": "  "},
        {"merchant": "x" * 201},
        {"date": "30/09/2026"},
        {"image_path": "0123456789abcdef0123456789abcdef"},  # can't be set directly
    ],
)
def test_invalid_details_are_rejected(client, body):
    base = {"date": "2026-09-30", "merchant": MERCHANT, "total_cents": 100}
    assert client.post(URL, json={**base, **body}).status_code == 422


def test_unknown_links_are_rejected(client, make_receipt):
    body = {"date": "2026-09-30", "merchant": "x", "total_cents": 1, "category_id": 999}
    assert client.post(URL, json=body).json()["error"]["code"] == "not_found"
    rid = make_receipt()["id"]
    assert client.patch(f"{URL}/{rid}", json={"transaction_id": 999}).status_code == 404
    assert client.patch(f"{URL}/{rid}", json={"merchant": None}).status_code == 422


def test_upload_is_encrypted_stripped_and_downloadable(client, make_receipt):
    rid = make_receipt()["id"]
    response = upload(client, rid, img.jpeg(), **{"Content-Type": "image/png"})
    assert response.status_code == 200, response.text
    assert response.json()["has_image"] is True

    [name] = stored_files(client)
    on_disk = (store(client).directory / name).read_bytes()
    assert img.SCAN not in on_disk and b"FAKE" not in on_disk  # encrypted

    download = client.get(f"{URL}/{rid}/image")
    assert download.status_code == 200
    assert download.content == img.clean_jpeg()  # EXIF/GPS gone
    assert download.headers["content-type"] == "image/jpeg"  # from the bytes, not the upload
    assert download.headers["content-disposition"] == f'inline; filename="receipt-{rid}.jpg"'
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["cache-control"] == "no-store"
    assert "sandbox" in download.headers["content-security-policy"]

    attached = client.get(f"{URL}/{rid}/image", params={"download": "true"})
    assert attached.headers["content-disposition"].startswith("attachment;")


@pytest.mark.parametrize(
    ("data", "mime", "extension"),
    [(img.png(), "image/png", "png"), (img.heic(), "image/heic", "heic")],
)
def test_png_and_heic(client, make_receipt, data, mime, extension):
    rid = make_receipt()["id"]
    assert upload(client, rid, data, **{"Content-Type": "image/jpeg"}).status_code == 200
    download = client.get(f"{URL}/{rid}/image")
    assert download.headers["content-type"] == mime
    assert download.headers["content-disposition"].endswith(f'.{extension}"')


@pytest.mark.parametrize(
    "data", [b"<html><script>alert(1)</script></html>", b"GIF89a fake", b"", img.jpeg()[:40]]
)
def test_non_images_are_rejected_whatever_they_claim(client, make_receipt, data):
    rid = make_receipt()["id"]
    response = upload(client, rid, data, **{"Content-Type": "image/jpeg"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "image_invalid"
    assert stored_files(client) == []
    assert client.get(f"{URL}/{rid}").json()["has_image"] is False


def test_too_large_upload_is_refused(client, make_receipt):
    rid = make_receipt()["id"]
    response = upload(client, rid, b"\xff\xd8\xff" + b"0" * MAX_IMAGE_BYTES)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "image_too_large"

    def chunks():  # no Content-Length: the limit is checked while reading
        for _ in range(4):
            yield b"0" * 1_048_576

    assert upload(client, rid, chunks()).status_code == 413
    assert stored_files(client) == []


def test_replacing_and_removing_the_photo_deletes_old_files(client, make_receipt):
    rid = make_receipt()["id"]
    upload(client, rid, img.jpeg())
    [first] = stored_files(client)
    upload(client, rid, img.png())
    [second] = stored_files(client)
    assert first != second
    assert client.get(f"{URL}/{rid}/image").headers["content-type"] == "image/png"

    response = client.delete(f"{URL}/{rid}/image")
    assert response.status_code == 200 and response.json()["has_image"] is False
    assert stored_files(client) == []
    assert client.get(f"{URL}/{rid}/image").json()["error"]["code"] == "no_image"


def test_deleting_a_receipt_deletes_its_photo(client, make_receipt):
    keep, gone = make_receipt()["id"], make_receipt()["id"]
    upload(client, keep, img.jpeg())
    upload(client, gone, img.png())
    assert len(stored_files(client)) == 2
    assert client.delete(f"{URL}/{gone}").status_code == 204
    assert len(stored_files(client)) == 1
    assert client.get(f"{URL}/{keep}/image").status_code == 200


def test_failed_save_leaves_no_file(client, make_receipt, monkeypatch):
    rid = make_receipt()["id"]

    def broken_commit(self):
        raise RuntimeError("fake database failure")

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", broken_commit)
    with pytest.raises(RuntimeError):
        upload(client, rid, img.jpeg())
    monkeypatch.undo()
    assert stored_files(client) == []
    assert client.get(f"{URL}/{rid}").json()["has_image"] is False


def test_missing_or_tampered_file(client, make_receipt):
    rid = make_receipt()["id"]
    upload(client, rid, img.jpeg())
    [name] = stored_files(client)
    path = store(client).directory / name
    blob = bytearray(path.read_bytes())
    blob[-1] ^= 1
    path.write_bytes(bytes(blob))
    assert client.get(f"{URL}/{rid}/image").json()["error"]["code"] == "image_unreadable"
    path.unlink()
    assert client.get(f"{URL}/{rid}/image").json()["error"]["code"] == "image_missing"


def test_orphan_files_are_cleaned_up_safely(client, make_receipt):
    rid = make_receipt()["id"]
    upload(client, rid, img.jpeg())
    [kept] = stored_files(client)
    files = store(client)
    orphan_old = files.path_for(files.save(b"leftover"))
    orphan_new = files.path_for(files.save(b"just saved"))
    half_written = files.directory / f".{'a' * 32}.bbf.{'b' * 32}.tmp"
    half_written.write_bytes(b"partial")
    unrelated = files.directory / "my-notes.txt"
    unrelated.write_bytes(b"not ours")
    an_hour_ago = time.time() - 2 * 3600
    for path in (orphan_old, half_written, unrelated, files.directory / kept):
        os.utime(path, (an_hour_ago, an_hour_ago))

    assert service.remove_orphan_files(client.app.state.engine, files) == 2
    assert sorted(stored_files(client)) == sorted([kept, orphan_new.name, "my-notes.txt"])
    assert client.get(f"{URL}/{rid}/image").status_code == 200


def test_cleanup_runs_at_start(make_client, make_receipt, client):
    files = store(client)
    orphan = files.path_for(files.save(b"leftover"))
    os.utime(orphan, (0, 0))
    make_client()  # a fresh start of the Home Base on the same data folder
    assert not orphan.exists()


def test_other_computers_cant_reach_receipts(make_client, make_receipt):
    rid = make_receipt()["id"]
    phone = make_client(peer="192.168.1.20")
    assert phone.get(f"{URL}/{rid}/image").status_code == 403
    assert phone.put(f"{URL}/{rid}/image", content=img.jpeg()).status_code == 403


def test_logs_never_hold_receipt_details(client, make_receipt, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    rid = make_receipt(total_cents=987_654)["id"]
    upload(client, rid, img.jpeg())
    client.get(f"{URL}/{rid}/image")
    monkeypatch.setattr(store(client), "delete", lambda _id: (_ for _ in ()).throw(OSError()))
    client.delete(f"{URL}/{rid}")
    assert "couldn't be deleted" in caplog.text
    for secret in (MERCHANT, "987654", "9876.54", "FAKE-LOCATION"):
        assert secret not in caplog.text
