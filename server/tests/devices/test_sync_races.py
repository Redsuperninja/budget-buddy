"""Sync edge cases: a phone removed mid-request, the replay watermark, and shared receipt IDs."""

import uuid

from fake_images import jpeg
from fake_phone import NOW, SNAPSHOT, Phone, pair_phone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_encode
from app.models import Device, Receipt, SeenNonce
from app.services.devices import envelope, snapshot, sync_receipts

RECEIPTS = "/api/sync/receipts"


def during_request(monkeypatch, action) -> None:
    """Run ``action`` after the token check and body read, just before the nonce is saved."""
    real = envelope.check_contract

    def check_contract(inner):
        action()
        return real(inner)

    monkeypatch.setattr(envelope, "check_contract", check_contract)


def device_row(phone: Phone) -> Device:
    with Session(phone.dashboard.app.state.engine) as session:
        return session.get(Device, phone.device_id)


def test_phone_removed_while_its_body_was_arriving_gets_nothing(phone, monkeypatch):
    revoke = lambda: phone.dashboard.post(f"/api/local/devices/{phone.device_id}/revoke")  # noqa: E731
    during_request(monkeypatch, revoke)
    response, _ = phone.call(SNAPSHOT)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "device_revoked"
    assert "box" not in response.json()  # plaintext: the old key is no longer trusted
    with Session(phone.dashboard.app.state.engine) as session:
        assert session.scalars(select(SeenNonce)).all() == []


def test_receipt_upload_is_not_saved_when_the_phone_was_removed_mid_request(phone, monkeypatch):
    revoke = lambda: phone.dashboard.post(f"/api/local/devices/{phone.device_id}/revoke")  # noqa: E731
    during_request(monkeypatch, revoke)
    item = {
        "client_id": str(uuid.uuid4()),
        "captured_at": "2026-09-20T12:00:00Z",
        "image": {"mime": "image/jpeg", "data": b64u_encode(b"\xff\xd8\xff")},
    }
    response, _ = phone.call(RECEIPTS, {"receipts": [item]})
    assert response.status_code == 401
    with Session(phone.dashboard.app.state.engine) as session:
        assert session.scalars(select(Receipt)).all() == []


def test_receipt_not_saved_when_phone_removed_just_before_its_commit(phone, monkeypatch):
    real = sync_receipts.create_receipt

    def create(*args, before_commit=None, **kwargs):
        phone.dashboard.post(f"/api/local/devices/{phone.device_id}/revoke")
        return real(*args, before_commit=before_commit, **kwargs)

    monkeypatch.setattr(sync_receipts, "create_receipt", create)
    item = photo_upload()
    response, _ = phone.call(RECEIPTS, {"receipts": [item]})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "device_revoked"
    with Session(phone.dashboard.app.state.engine) as session:
        assert session.scalars(select(Receipt)).all() == []
    assert list(phone.dashboard.app.state.receipt_store.directory.iterdir()) == []


def test_snapshot_not_sent_when_phone_removed_while_it_was_built(phone, monkeypatch):
    real = snapshot.build_snapshot

    def build(*args, **kwargs):
        phone.dashboard.post(f"/api/local/devices/{phone.device_id}/revoke")
        return real(*args, **kwargs)

    monkeypatch.setattr(snapshot, "build_snapshot", build)
    response, _ = phone.call(SNAPSHOT)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "device_revoked"
    assert "box" not in response.json()


def test_watermark_never_moves_backwards(phone, monkeypatch):
    def another_request_moved_it_on():
        with Session(phone.dashboard.app.state.engine) as session:
            session.get(Device, phone.device_id).nonce_watermark = NOW + 5000
            session.commit()

    during_request(monkeypatch, another_request_moved_it_on)
    phone.ok(SNAPSHOT)
    assert device_row(phone).nonce_watermark == NOW + 5000


def upload(client_id: str) -> dict:
    return {
        "client_id": client_id,
        "captured_at": "2026-09-20T12:00:00Z",
        "merchant": "Fake Shop",
        "image": None,
    }


def photo_upload() -> dict:
    image = {"mime": "image/jpeg", "data": b64u_encode(jpeg())}
    return upload(str(uuid.uuid4())) | {"image": image}


def test_receipt_id_from_another_phone_is_rejected_not_duplicate(dashboard, phone):
    other = pair_phone(dashboard, "Second Phone")
    item = photo_upload()
    first = phone.ok(RECEIPTS, {"receipts": [item]})["results"][0]
    assert first["status"] == "accepted"
    again = phone.ok(RECEIPTS, {"receipts": [item]})["results"][0]
    assert again == {"client_id": item["client_id"], "status": "duplicate", "receipt_id": 1}
    stolen = other.ok(RECEIPTS, {"receipts": [item]})["results"][0]
    assert stolen["status"] == "rejected" and stolen["reason"] == "invalid_field"
    assert "receipt_id" not in stolen
    with Session(dashboard.app.state.engine) as session:
        (row,) = session.scalars(select(Receipt)).all()
        assert row.device_id == phone.device_id
