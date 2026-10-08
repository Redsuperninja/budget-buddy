"""Pairing (roadmap #14): POST /api/pair, normal flow and its edges."""

import logging
import os

import pytest
from contract_vectors import VECTOR_CODE
from fake_phone import (
    LAN_HOST,
    NOW,
    PAIR,
    error_code,
    make_request,
    open_reply,
    pair_once,
)
from nacl.public import PrivateKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_encode
from app.db import database_path
from app.models import Device, PairingNonce, PairingSession
from app.services import devices as device_service
from app.services import pairing as pairing_service


def test_deeply_nested_json_is_a_plain_400(app_client, start):
    _, phone = app_client
    start()
    body = b"[" * 8000 + b"]" * 8000
    response = phone.post(
        PAIR, content=body, headers=LAN_HOST | {"Content-Type": "application/json"}
    )
    assert response.status_code == 400 and error_code(response) == "bad_request"


def test_full_pairing_then_token_works_and_secrets_not_in_the_database(app_client, start, data_dir):
    dashboard, phone = app_client
    qr = start()["payload"]
    response, shared, nonce = pair_once(phone, qr)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = open_reply(response, shared, nonce)["data"]

    with Session(dashboard.app.state.engine) as session:
        device = device_service.authenticate_token(session, data["token"])
        assert device.id == data["device_id"]
    database = b"".join(
        p.read_bytes() for p in database_path(data_dir).parent.glob("budget.db*") if p.is_file()
    )
    assert data["token"].encode() not in database
    assert data["sync_key"].encode() not in database

    listed = dashboard.get("/api/local/devices").json()
    assert [d["name"] for d in listed] == ["Test Phone"]
    assert not {"token", "token_hash", "sync_key"} & set(listed[0])


def test_code_works_only_once(app_client, start):
    _, phone = app_client
    qr = start()["payload"]
    assert pair_once(phone, qr)[0].status_code == 200
    second = pair_once(phone, qr)[0]
    assert second.status_code == 410 and error_code(second) == "pairing_expired"


def test_two_phones_racing_for_one_code_only_one_wins(app_client, start):
    dashboard, _ = app_client
    qr = start()["payload"]
    body, _, _ = make_request(qr["pair_pub"], qr["code"])
    with Session(dashboard.app.state.engine) as session:
        pairing = pairing_service.require_active_session(session, NOW)
        # The other phone finishes between our "is there a session?" check and our claim.
        with Session(dashboard.app.state.engine) as other:
            other.execute(
                PairingSession.__table__.update()
                .where(PairingSession.id == pairing.id)
                .values(used_at=NOW)
            )
            other.commit()
        result = pairing_service.pair(
            session, pairing, body, now=NOW, server_id="x", server_name="Home Base"
        )
    assert result.status == 410
    with Session(dashboard.app.state.engine) as session:
        assert session.scalars(select(Device)).all() == []


def test_new_qr_cancels_the_old_one(app_client, start):
    _, phone = app_client
    old = start()["payload"]
    new = start()["payload"]
    assert old["code"] != new["code"] and old["pair_pub"] != new["pair_pub"]
    assert error_code(pair_once(phone, old)[0]) == "decrypt_failed"  # old key is gone
    assert pair_once(phone, new)[0].status_code == 200


def test_expired_code(app_client, start):
    dashboard, phone = app_client
    qr = start()["payload"]
    dashboard.app.state.clock = lambda: NOW + 601
    response = pair_once(phone, qr, ts=NOW + 601)[0]
    assert response.status_code == 410 and error_code(response) == "pairing_expired"
    with Session(dashboard.app.state.engine) as session:
        assert session.scalars(select(PairingSession)).one().pair_sk is None  # key erased


def test_wrong_code_is_an_encrypted_error_and_five_end_the_session(app_client, start):
    dashboard, phone = app_client
    qr = start()["payload"]
    wrong = b64u_encode(os.urandom(16))
    for attempt in range(5):
        response, shared, nonce = pair_once(phone, qr | {"code": wrong})
        assert response.status_code == 410, attempt
        assert open_reply(response, shared, nonce)["error"]["code"] == "pairing_expired"
    # Session is cancelled: even the right code can't be used now.
    response = pair_once(phone, qr)[0]
    assert response.status_code == 410 and error_code(response) == "pairing_expired"
    with Session(dashboard.app.state.engine) as session:
        assert session.scalars(select(Device)).all() == []


def test_garbage_does_not_count_against_the_user(app_client, start):
    _, phone = app_client
    qr = start()["payload"]
    for _ in range(6):
        body, _, _ = make_request(qr["pair_pub"], qr["code"])
        body["box"] = b64u_encode(os.urandom(80))  # can't be opened
        response = phone.post(PAIR, json=body, headers=LAN_HOST)
        assert response.status_code == 401 and error_code(response) == "decrypt_failed"
    assert pair_once(phone, qr)[0].status_code == 200


def test_replayed_request_is_refused(app_client, start):
    _, phone = app_client
    qr = start()["payload"]
    body, shared, nonce = make_request(qr["pair_pub"], b64u_encode(os.urandom(16)))
    first = phone.post(PAIR, json=body, headers=LAN_HOST)
    assert open_reply(first, shared, nonce)["error"]["code"] == "pairing_expired"  # wrong code
    again = phone.post(PAIR, json=body, headers=LAN_HOST)
    assert again.status_code == 409
    assert open_reply(again, shared, nonce)["error"]["code"] == "replay"


def test_replayed_nonce_is_stored_as_bytes(app_client, start):
    dashboard, phone = app_client
    qr = start()["payload"]
    nonce = os.urandom(24)
    pair_once(phone, qr | {"code": b64u_encode(os.urandom(16))}, nonce=nonce)
    with Session(dashboard.app.state.engine) as session:
        assert session.scalars(select(PairingNonce.nonce)).one() == nonce


def test_no_active_session(app_client):
    _, phone = app_client
    body, _, _ = make_request("YFpyXSpK3-6xop4X7dYhwbdZPujNvESsbEq24vgF0jw", VECTOR_CODE)
    response = phone.post(PAIR, json=body, headers=LAN_HOST)
    assert response.status_code == 410 and error_code(response) == "pairing_expired"


@pytest.mark.parametrize("skew", [301, -301])
def test_clock_skew_is_plain_and_has_server_time(app_client, start, skew):
    _, phone = app_client
    qr = start()["payload"]
    response = pair_once(phone, qr, ts=NOW + skew)[0]
    assert response.status_code == 400 and error_code(response) == "clock_skew"
    assert response.json()["error"]["server_time"] == NOW


def test_edge_of_clock_window_is_fine(app_client, start):
    _, phone = app_client
    assert pair_once(phone, start()["payload"], ts=NOW - 300)[0].status_code == 200


def test_wrong_phone_key_cant_open(app_client, start):
    _, phone = app_client
    qr = start()["payload"]
    body, _, _ = make_request(qr["pair_pub"], qr["code"])
    body["phone_pub"] = b64u_encode(bytes(PrivateKey.generate().public_key))  # swapped in transit
    response = phone.post(PAIR, json=body, headers=LAN_HOST)
    assert response.status_code == 401 and error_code(response) == "decrypt_failed"


def test_all_zero_phone_key_is_a_bad_request(app_client, start):
    _, phone = app_client
    qr = start()["payload"]
    body, _, _ = make_request(qr["pair_pub"], qr["code"])
    body["phone_pub"] = b64u_encode(bytes(32))
    assert phone.post(PAIR, json=body, headers=LAN_HOST).status_code == 400


@pytest.mark.parametrize(
    "override",
    [
        {"type": "res"},
        {"ts": NOW + 1},
        {"method": "GET"},
        {"path": "/api/sync/snapshot"},
    ],
)
def test_inner_fields_must_match(app_client, start, override):
    _, phone = app_client
    response = pair_once(phone, start()["payload"], inner_overrides=override)[0]
    assert response.status_code == 401 and error_code(response) == "decrypt_failed"


def test_unknown_contract_is_an_encrypted_426(app_client, start):
    _, phone = app_client
    response, shared, nonce = pair_once(phone, start()["payload"], inner_overrides={"contract": 2})
    assert response.status_code == 426
    error = open_reply(response, shared, nonce)["error"]
    assert error["code"] == "update_needed" and error["supported"] == [1]


@pytest.mark.parametrize(
    "overrides",
    [
        {"platform": "windows"},
        {"device_name": ""},
        {"device_name": "x" * 51},
        {"device_name": "bad\nname"},
        {"code": "short"},
        {"app_version": 1},
    ],
)
def test_bad_inner_data_is_an_encrypted_400(app_client, start, overrides):
    _, phone = app_client
    response, shared, nonce = pair_once(phone, start()["payload"], data_overrides=overrides)
    assert response.status_code == 400
    assert open_reply(response, shared, nonce)["error"]["code"] == "bad_request"


def test_old_envelope_version_is_426(app_client, start):
    _, phone = app_client
    qr = start()["payload"]
    body, _, _ = make_request(qr["pair_pub"], qr["code"])
    response = phone.post(PAIR, json=body | {"v": 2}, headers=LAN_HOST)
    assert response.status_code == 426 and response.json()["error"]["supported"] == [1]


@pytest.mark.parametrize(
    "change",
    [
        {"nonce": "AAAA"},
        {"nonce": "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3="},
        {"box": "AAAA"},
        {"box": 5},
        {"phone_pub": "AAAA"},
        {"ts": "1790000000"},
        {"ts": True},
    ],
)
def test_malformed_envelope_is_a_plain_400(app_client, start, change):
    _, phone = app_client
    qr = start()["payload"]
    body, _, _ = make_request(qr["pair_pub"], qr["code"])
    response = phone.post(PAIR, json=body | change, headers=LAN_HOST)
    assert response.status_code == 400 and error_code(response) == "bad_request"


def test_missing_envelope_fields_and_non_json(app_client, start):
    _, phone = app_client
    start()
    assert phone.post(PAIR, json={}, headers=LAN_HOST).status_code == 400
    assert phone.post(PAIR, json=[1], headers=LAN_HOST).status_code == 400
    bad = phone.post(
        PAIR, content=b"{nope", headers=LAN_HOST | {"Content-Type": "application/json"}
    )
    assert bad.status_code == 400 and error_code(bad) == "bad_request"
    wrong_type = phone.post(PAIR, content=b"{}", headers=LAN_HOST | {"Content-Type": "text/plain"})
    assert wrong_type.status_code == 400 and error_code(wrong_type) == "bad_request"


def test_body_over_16_kib_is_refused_while_streaming(app_client, start):
    _, phone = app_client
    start()
    headers = LAN_HOST | {"Content-Type": "application/json"}

    def chunks():  # no Content-Length: chunked upload
        for _ in range(20):
            yield b" " * 1024

    response = phone.post(PAIR, content=chunks(), headers=headers)
    assert response.status_code == 413 and error_code(response) == "too_large"
    big = phone.post(PAIR, content=b" " * (16 * 1024 + 1), headers=headers)
    assert big.status_code == 413


def test_rate_limit_is_ten_a_minute_per_address(app_client, start):
    dashboard, phone = app_client
    start()
    for _ in range(10):
        assert phone.post(PAIR, json={}, headers=LAN_HOST).status_code == 400
    response = phone.post(PAIR, json={}, headers=LAN_HOST)
    assert response.status_code == 429 and error_code(response) == "too_many_attempts"
    # Per address: someone else is not locked out, and the window slides.
    other = dashboard.app.state.pair_limiter
    assert other.allow("192.168.1.99", 0) is True


def test_rate_limit_window_slides():
    from app.ratelimit import RateLimiter

    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("a", 0) and limiter.allow("a", 1)
    assert not limiter.allow("a", 2)
    assert limiter.allow("a", 61)


def test_pair_answers_the_home_network_but_only_with_the_right_host(app_client, start):
    _, phone = app_client
    qr = start()["payload"]
    body, _, _ = make_request(qr["pair_pub"], qr["code"])
    bad = phone.post(PAIR, json=body, headers={"Host": "192.168.1.21:8765"})
    assert bad.status_code == 403 and error_code(bad) == "bad_host"
    assert phone.post(PAIR, json=body, headers=LAN_HOST).status_code == 200


def test_pair_refuses_other_networks(make_client):
    outside = make_client("203.0.113.9", headers={})
    assert outside.post(PAIR, json={}, headers=LAN_HOST).status_code == 403


def test_nothing_secret_is_logged(app_client, start, caplog):
    _, phone = app_client
    with caplog.at_level(logging.DEBUG):
        qr = start()["payload"]
        response, shared, nonce = pair_once(phone, qr)
        data = open_reply(response, shared, nonce)["data"]
    logged = caplog.text
    for secret in (qr["code"], data["token"], data["sync_key"], qr["pair_pub"]):
        assert secret not in logged
