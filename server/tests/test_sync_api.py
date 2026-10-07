"""Encrypted sync (roadmap #15): envelope rules, replay protection, limits, ack, revoke.

Uses a fake phone that pairs through the real flow (tests/sync_helpers.py), and the sync
contract's test vectors (section 4.7). Fake data only.
"""

import json

import pytest
from fastapi.testclient import TestClient
from nacl.secret import SecretBox
from sqlalchemy import select
from sqlalchemy.orm import Session
from sync_helpers import LAN_BASE, LAN_PEER, NOW, Phone, pair_phone

from app.bodylimit import read_limited
from app.crypto.b64url import b64u_decode, b64u_encode
from app.errors import ApiError
from app.models import Device, SeenNonce
from app.services import envelope

SNAPSHOT = "/api/sync/snapshot"
ACK = "/api/sync/ack"
ACK_DATA = {
    "snapshot_generated_at": "2026-09-21T08:13:20Z",
    "receipts_uploaded": 2,
    "app_version": "1.0.1",
}


@pytest.fixture
def dashboard(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def phone(dashboard) -> Phone:
    return pair_phone(dashboard)


def code_of(response) -> str:
    return response.json()["error"]["code"]


def seen_nonce_count(phone: Phone) -> int:
    with Session(phone.dashboard.app.state.engine) as session:
        return len(session.scalars(select(SeenNonce)).all())


def watermark(phone: Phone) -> int:
    with Session(phone.dashboard.app.state.engine) as session:
        return session.get(Device, phone.device_id).nonce_watermark


# --- contract section 4.7 vectors ----------------------------------------------------------

KEY = b64u_decode("AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8", 32)
V1 = {
    "v": 1,
    "nonce": "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3",
    "ts": 1790000000,
    "box": (
        "h3tnJpseU-mZcMCYFrdbMYp7Odw9QnisK0cwHy5klYDKkIe6xiATRIxGA6LyN46Q0n-4rJ-LQ-3zIQDf1_FcItKiw"
        "usyFNue2TJQ6OB3Ly7bIX6xJfqbUjm4RRhuulXPJek3maWpfGGPCQ12_-DORKg"
    ),
}
V2 = {
    "v": 1,
    "nonce": "QEFCQ0RFRkdISUpLTE1OT1BRUlNUVVZX",
    "ts": 1790000001,
    "box": (
        "hlFMv8abBA-l4oJaaRR4wDE1IQBKNJkQ5CsUEkqleIW9FXxlWnpv-NTlEvrI9aEmsRZTM6f0g20QNU0Ve5s5QMvnTB"
        "_rzYAzxKj6ykod04XRmOGWeePezi-F5XD-bD8BYnJcPJt9bVe9XcBjvFOnpeuQUTyfJAe-DC--kT6NYdUvBUQi5_an"
        "PPrja69GQjnA3ZUMVuf2DQ"
    ),
}


def test_vector_1_request_opens_through_the_envelope_module():
    outer = envelope.parse_outer(V1)
    inner = envelope.open_request(KEY, outer, path=SNAPSHOT)
    assert inner == {
        "type": "req",
        "ts": 1790000000,
        "method": "POST",
        "path": SNAPSHOT,
        "contract": 1,
        "data": {},
    }


def test_vector_1_is_refused_for_another_path():
    with pytest.raises(ApiError) as caught:
        envelope.open_request(KEY, envelope.parse_outer(V1), path=ACK)
    assert caught.value.code == "decrypt_failed"


def test_vector_2_response_decrypts_to_the_expected_text():
    plain = SecretBox(KEY).decrypt(b64u_decode(V2["box"]), b64u_decode(V2["nonce"], 24))
    assert plain.decode("utf-8") == (
        '{"type":"res","ts":1790000001,"re":"ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3","status":200,'
        '"data":{"merchant":"Café Olé","total_cents":1234}}'
    )


def test_seal_makes_a_response_the_phone_can_open():
    reply = envelope.seal(KEY, V1["nonce"], NOW, 200, data={"merchant": "Café Olé"})
    plain = SecretBox(KEY).decrypt(b64u_decode(reply["box"]), b64u_decode(reply["nonce"], 24))
    inner = json.loads(plain)
    assert inner["type"] == "res" and inner["re"] == V1["nonce"] and inner["status"] == 200
    assert inner["data"] == {"merchant": "Café Olé"}


def test_vector_3_tampered_box_is_decrypt_failed():
    box = bytearray(b64u_decode(V1["box"]))
    box[-1] ^= 1
    outer = envelope.parse_outer(V1 | {"box": b64u_encode(bytes(box))})
    with pytest.raises(ApiError) as caught:
        envelope.open_request(KEY, outer, path=SNAPSHOT)
    assert caught.value.code == "decrypt_failed"


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


# --- who may call, and from where -----------------------------------------------------------


def test_lan_phone_reaches_sync_but_not_the_dashboard_routes(phone):
    assert phone.call(SNAPSHOT)[0].status_code == 200
    response = phone.http.get("/api/local/accounts")
    assert response.status_code == 403 and code_of(response) == "not_this_computer"


def test_public_addresses_get_not_home_network(dashboard, phone):
    outside = TestClient(dashboard.app, client=("203.0.113.7", 50000), base_url=LAN_BASE)
    response = outside.post(SNAPSHOT, content=b"{}")
    assert response.status_code == 403 and code_of(response) == "not_home_network"


def test_unknown_host_header_is_bad_host(phone):
    response, _ = phone.call(SNAPSHOT, headers={"Host": "evil.example:8765"})
    assert response.status_code == 403 and code_of(response) == "bad_host"


# --- token checks come first --------------------------------------------------------------


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer", "Bearer "])
def test_missing_token_is_not_paired(phone, header):
    headers = {} if header is None else {"Authorization": header}
    response, _ = phone.call(SNAPSHOT, token=None, headers=headers)
    assert response.status_code == 401 and code_of(response) == "not_paired"


def test_unknown_token_is_not_paired(phone):
    response, _ = phone.call(SNAPSHOT, token=b64u_encode(bytes(32)))
    assert response.status_code == 401 and code_of(response) == "not_paired"


@pytest.mark.parametrize(
    "token", ["short", "AAAAA", "x" * 43 + "=", "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3"]
)
def test_malformed_token_is_bad_request(phone, token):
    response, _ = phone.call(SNAPSHOT, token=token)
    assert response.status_code == 400 and code_of(response) == "bad_request"


def test_token_is_checked_before_the_body_is_read(phone):
    reads = []

    def body():
        for _ in range(100):
            reads.append(1)
            yield b"x" * 1024

    response = phone.http.post(
        SNAPSHOT, content=body(), headers={"Authorization": f"Bearer {b64u_encode(bytes(32))}"}
    )
    assert response.status_code == 401
    assert len(reads) < 100  # the server did not drain the upload


def test_revoked_device_is_refused_and_its_nonces_deleted(phone, dashboard):
    phone.ok(SNAPSHOT)
    assert seen_nonce_count(phone) == 1
    assert dashboard.post(f"/api/local/devices/{phone.device_id}/revoke").status_code == 200
    assert seen_nonce_count(phone) == 0
    response, _ = phone.call(SNAPSHOT)
    assert response.status_code == 401 and code_of(response) == "device_revoked"
    with Session(dashboard.app.state.engine) as session:
        device = session.get(Device, phone.device_id)
        assert device.revoked and device.sync_key is None


# --- body checks --------------------------------------------------------------------------


def test_wrong_content_type_is_bad_request(phone):
    response, _ = phone.call(SNAPSHOT, headers={"Content-Type": "text/plain"})
    assert response.status_code == 400 and code_of(response) == "bad_request"


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"v":1}', b""])
def test_garbage_body_is_bad_request(phone, body):
    response, _ = phone.call(SNAPSHOT, body=body)
    assert response.status_code == 400 and code_of(response) == "bad_request"


def test_bad_envelope_fields_are_bad_request(phone):
    good, _ = phone.envelope(SNAPSHOT)
    for change in (
        {"nonce": b64u_encode(bytes(23))},
        {"nonce": "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3="},
        {"box": "AAAA"},  # 3 bytes: shorter than the 16-byte tag
        {"box": good["box"] + "\n"},
        {"ts": "1790000000"},
        {"ts": True},
    ):
        response, _ = phone.call(SNAPSHOT, body=good | change)
        assert response.status_code == 400, change
        assert code_of(response) == "bad_request", change


def test_unsupported_envelope_version_is_update_needed(phone):
    good, _ = phone.envelope(SNAPSHOT)
    response, _ = phone.call(SNAPSHOT, body=good | {"v": 2})
    assert response.status_code == 426 and code_of(response) == "update_needed"
    assert response.json()["error"]["supported"] == [1]


def test_oversize_body_is_413_by_content_length(phone):
    response, _ = phone.call(SNAPSHOT, body=b"x" * (16 * 1024 + 1))
    assert response.status_code == 413 and code_of(response) == "too_large"


def test_oversize_body_is_413_while_streaming(phone):
    def body():  # no Content-Length: the server has to count as it reads
        for _ in range(100):
            yield b"x" * 4096

    response = phone.http.post(
        SNAPSHOT,
        content=body(),
        headers={"Authorization": f"Bearer {phone.token}", "Content-Type": "application/json"},
    )
    assert response.status_code == 413 and code_of(response) == "too_large"


def test_reader_stops_pulling_chunks_at_the_limit():
    import asyncio

    pulled = []

    class FakeRequest:
        headers = {}  # no Content-Length

        async def stream(self):
            for _ in range(1000):
                pulled.append(1)
                yield b"x" * 1024

    with pytest.raises(ApiError) as caught:
        asyncio.run(read_limited(FakeRequest(), 16 * 1024))
    assert caught.value.status == 413 and len(pulled) == 17


def test_body_at_the_limit_is_still_read(phone):
    response, _ = phone.call(SNAPSHOT, body=b" " * (16 * 1024))
    assert response.status_code == 400  # read in full, then rejected as not an envelope


# --- clock, decrypt, inner checks -----------------------------------------------------------


def test_clock_skew_is_plaintext_with_server_time(phone):
    for ts in (NOW + 301, NOW - 301):
        response, _ = phone.call(SNAPSHOT, ts=ts)
        assert response.status_code == 400 and code_of(response) == "clock_skew"
        assert response.json()["error"]["server_time"] == NOW
    assert phone.call(SNAPSHOT, ts=NOW + 300)[0].status_code == 200


def test_wrong_key_is_decrypt_failed(phone):
    response, _ = phone.call(SNAPSHOT, key=bytes(32))
    assert response.status_code == 401 and code_of(response) == "decrypt_failed"


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
    assert response.status_code == 401 and code_of(response) == "decrypt_failed"


def test_box_for_another_endpoint_cannot_be_replayed_here(phone):
    sent, _ = phone.envelope(ACK, ACK_DATA)
    response, _ = phone.call(SNAPSHOT, body=sent)
    assert response.status_code == 401 and code_of(response) == "decrypt_failed"


def test_unsupported_contract_is_encrypted_update_needed(phone):
    response, nonce = phone.call(SNAPSHOT, inner={"contract": 2})
    assert response.status_code == 426
    error = phone.open(response, nonce)["error"]
    assert error["code"] == "update_needed" and error["supported"] == [1]


def test_other_devices_key_does_not_open_this_device(dashboard, phone):
    other = pair_phone(dashboard, "Second Phone")
    response, _ = phone.call(SNAPSHOT, key=other.key)
    assert response.status_code == 401 and code_of(response) == "decrypt_failed"


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
    assert response.status_code == 400 and code_of(response) == "clock_skew"


def test_clock_jumping_forward_does_not_lock_the_phone_out(phone):
    phone.dashboard.app.state.clock = lambda: NOW + 100_000  # computer's clock is wrong
    response, _ = phone.call(SNAPSHOT, ts=NOW)
    assert response.status_code == 400 and code_of(response) == "clock_skew"
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

    monkeypatch.setattr("app.services.sync.snapshot.build_snapshot", boom)
    response, nonce = phone.call(SNAPSHOT)
    assert response.status_code == 500
    assert "secret detail" not in response.text
    error = phone.open(response, nonce)["error"]
    assert error["code"] == "server_error" and "secret" not in error["message"]
    assert "budget.db" not in json.dumps(error)


def test_all_routes_answer_post_only(phone):
    assert phone.http.get(SNAPSHOT).status_code == 405
