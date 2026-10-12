"""Encrypted sync (roadmap #15): the happy path, clock and decrypt, replay protection, ack.

Uses a fake phone that pairs through the real flow (tests/fake_phone.py). Fake data only.
"""

import json

import pytest
from fake_phone import (
    ACK,
    LAN_BASE,
    LAN_PEER,
    NOW,
    SNAPSHOT,
    Phone,
    error_code,
    pair_phone,
    seen_nonce_count,
)
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_encode
from app.models import Device

ACK_DATA = {
    "snapshot_generated_at": "2026-09-21T08:13:20Z",
    "receipts_uploaded": 2,
    "app_version": "1.0.1",
}


def watermark(phone: Phone) -> int:
    with Session(phone.dashboard.app.state.engine) as session:
        return session.get(Device, phone.device_id).nonce_watermark


# --- happy path ---------------------------------------------------------------------------


def test_snapshot_ack_flow_with_a_real_paired_phone(phone, dashboard):
    snapshot = phone.ok(SNAPSHOT)
    assert snapshot["contract"] == 1
    assert snapshot["server_id"] == dashboard.app.state.server_id

    assert dashboard.get("/api/local/devices").json()[0]["last_sync_at"] is None
    reply = phone.ok(ACK, ACK_DATA)
    assert reply["last_sync_at"].endswith("Z")
    device = dashboard.get("/api/local/devices").json()[0]
    assert device["last_sync_at"] is not None and device["app_version"] == "1.0.1"


def test_replies_are_not_cached_and_have_no_cors_headers(phone):
    response, _ = phone.call(SNAPSHOT)
    assert response.headers["cache-control"] == "no-store"
    assert not [h for h in response.headers if h.lower().startswith("access-control-")]
    options, _ = phone.call(SNAPSHOT, headers={"Origin": "https://evil.example"})
    assert not [h for h in options.headers if h.lower().startswith("access-control-")]


# --- clock, decrypt, inner checks -----------------------------------------------------------


def test_clock_skew_is_plaintext_with_server_time(phone):
    for ts in (NOW + 301, NOW - 301):
        response, _ = phone.call(SNAPSHOT, ts=ts)
        assert response.status_code == 400 and error_code(response) == "clock_skew"
        assert response.json()["error"]["server_time"] == NOW
    assert phone.call(SNAPSHOT, ts=NOW + 300)[0].status_code == 200


def test_wrong_key_is_decrypt_failed(phone):
    response, _ = phone.call(SNAPSHOT, key=bytes(32))
    assert response.status_code == 401 and error_code(response) == "decrypt_failed"


@pytest.mark.parametrize(
    "inner",
    [
        {"type": "res"},
        {"ts": NOW - 1},
        {"method": "GET"},
        {"path": "/api/sync/ack"},
    ],
)
def test_inner_request_must_match_the_call(phone, inner):
    response, _ = phone.call(SNAPSHOT, inner=inner)
    assert response.status_code == 401 and error_code(response) == "decrypt_failed"


def test_box_for_another_endpoint_cannot_be_replayed_here(phone):
    sent, _ = phone.envelope(ACK, ACK_DATA)
    response, _ = phone.call(SNAPSHOT, body=sent)
    assert response.status_code == 401 and error_code(response) == "decrypt_failed"


def test_unsupported_contract_is_encrypted_update_needed(phone):
    response, nonce = phone.call(SNAPSHOT, inner={"contract": 2})
    assert response.status_code == 426
    error = phone.open(response, nonce)["error"]
    assert error["code"] == "update_needed" and error["supported"] == [1]


def test_other_devices_key_does_not_open_this_device(dashboard, phone):
    other = pair_phone(dashboard, "Second Phone")
    response, _ = phone.call(SNAPSHOT, key=other.key)
    assert response.status_code == 401 and error_code(response) == "decrypt_failed"


# --- replay protection --------------------------------------------------------------------


def test_same_request_twice_is_an_encrypted_replay(phone):
    sent, nonce = phone.envelope(SNAPSHOT)
    assert phone.call(SNAPSHOT, body=sent)[0].status_code == 200
    response, _ = phone.call(SNAPSHOT, body=sent)
    assert response.status_code == 409
    error = phone.open(response, nonce)["error"]
    assert error["code"] == "replay" and "interrupted" in error["message"]


def test_replay_is_per_device(dashboard, phone):
    other = pair_phone(dashboard, "Second Phone")
    nonce = bytes(range(24))
    assert phone.call(SNAPSHOT, nonce=nonce)[0].status_code == 200
    assert other.call(SNAPSHOT, nonce=nonce)[0].status_code == 200


def test_nonce_is_remembered_across_restarts(make_client, phone):
    sent, _ = phone.envelope(SNAPSHOT)
    assert phone.call(SNAPSHOT, body=sent)[0].status_code == 200
    restarted = make_client()  # a new app on the same data folder
    restarted.app.state.clock = lambda: NOW
    again = Phone(
        restarted,
        TestClient(restarted.app, client=LAN_PEER, base_url=LAN_BASE),
        phone.token,
        b64u_encode(phone.key),
        phone.device_id,
    )
    response, _ = again.call(SNAPSHOT, body=sent)
    assert response.status_code == 409


def test_watermark_moves_only_with_accepted_requests(phone):
    assert watermark(phone) == 0
    phone.call(SNAPSHOT, ts=NOW - 400)  # outside the window: refused, nothing moves
    assert watermark(phone) == 0
    phone.ok(SNAPSHOT)
    assert watermark(phone) == NOW - 600
    phone.call(SNAPSHOT, key=bytes(32))  # can't be opened: nothing moves
    assert watermark(phone) == NOW - 600


def test_watermark_prunes_old_nonces_and_blocks_the_gap(phone):
    phone.ok(SNAPSHOT)
    assert seen_nonce_count(phone) == 1
    phone.dashboard.app.state.clock = lambda: NOW + 1000
    phone.ok(SNAPSHOT, ts=NOW + 1000)
    assert watermark(phone) == NOW + 400
    assert seen_nonce_count(phone) == 1  # the first request's nonce was pruned
    # The pruned range can't be used to replay: anything below the watermark is refused.
    phone.dashboard.app.state.clock = lambda: NOW
    response, _ = phone.call(SNAPSHOT, ts=NOW)
    assert response.status_code == 400 and error_code(response) == "clock_skew"


def test_clock_jumping_forward_does_not_lock_the_phone_out(phone):
    phone.dashboard.app.state.clock = lambda: NOW + 100_000  # computer's clock is wrong
    response, _ = phone.call(SNAPSHOT, ts=NOW)
    assert response.status_code == 400 and error_code(response) == "clock_skew"
    assert watermark(phone) == 0
    phone.dashboard.app.state.clock = lambda: NOW  # fixed again
    assert phone.call(SNAPSHOT, ts=NOW)[0].status_code == 200


# --- ack and errors --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        {"snapshot_generated_at": "yesterday"},
        {"snapshot_generated_at": 5},
        {"receipts_uploaded": -1},
        {"receipts_uploaded": True},
        {"receipts_uploaded": "2"},
        {"app_version": "x" * 33},
        {"app_version": None},
    ],
)
def test_ack_with_bad_fields_is_an_encrypted_bad_request(phone, change):
    response, nonce = phone.call(ACK, ACK_DATA | change)
    assert response.status_code == 400
    assert phone.open(response, nonce)["error"]["code"] == "bad_request"


def test_bad_data_errors_still_use_up_the_nonce(phone):
    sent, _ = phone.envelope(ACK, {})
    assert phone.call(ACK, body=sent)[0].status_code == 400
    assert phone.call(ACK, body=sent)[0].status_code == 409


def test_unexpected_failure_is_a_fixed_encrypted_server_error(phone, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("secret detail /home/user/budget.db")

    monkeypatch.setattr("app.services.devices.sync.snapshot.build_snapshot", boom)
    response, nonce = phone.call(SNAPSHOT)
    assert response.status_code == 500
    assert "secret detail" not in response.text
    error = phone.open(response, nonce)["error"]
    assert error["code"] == "server_error" and "secret" not in error["message"]
    assert "budget.db" not in json.dumps(error)


def test_all_routes_answer_post_only(phone):
    assert phone.http.get(SNAPSHOT).status_code == 405
