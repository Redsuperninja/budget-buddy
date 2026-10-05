"""Pairing (roadmap #14): start a QR, POST /api/pair, list and remove phones.

Includes the sync contract's test vectors (§4.7). Fake data only; the example address is a
private one (192.168.1.20) set up in conftest.
"""

import hashlib
import json
import logging
import os
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient
from nacl.public import Box, PrivateKey, PublicKey
from nacl.secret import SecretBox
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.crypto.b64url import b64u_decode, b64u_encode
from app.db import database_path
from app.models import Device, PairingNonce, PairingSession
from app.services import devices as device_service
from app.services import pairing as pairing_service

NOW = 1790000000
PAIR = "/api/pair"
LAN_HOST = {"Host": "192.168.1.20:8765"}


def _error_code(response) -> str:
    return response.json()["error"]["code"]


# --- contract §4.7 vectors for the shared helpers ----------------------------------------

KEY = b64u_decode("AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8", 32)
V1_BOX = (
    "h3tnJpseU-mZcMCYFrdbMYp7Odw9QnisK0cwHy5klYDKkIe6xiATRIxGA6LyN46Q0n-4rJ-LQ-3zIQDf1_FcItKiwusyFNue2TJQ"
    "6OB3Ly7bIX6xJfqbUjm4RRhuulXPJek3maWpfGGPCQ12_-DORKg"
)
V1_NONCE = "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3"


def test_vector_1_request_box_opens():
    plain = SecretBox(KEY).decrypt(b64u_decode(V1_BOX), b64u_decode(V1_NONCE, 24))
    assert plain == (
        b'{"type":"req","ts":1790000000,"method":"POST","path":"/api/sync/snapshot",'
        b'"contract":1,"data":{}}'
    )


def test_vector_3_tampered_box_fails():
    from nacl.exceptions import CryptoError

    box = bytearray(b64u_decode(V1_BOX))
    box[-1] ^= 1
    with pytest.raises(CryptoError):
        SecretBox(KEY).decrypt(bytes(box), b64u_decode(V1_NONCE, 24))


@pytest.mark.parametrize(
    ("text", "length"),
    [
        ("Zk3pR7tQ1xYb9mWc2nLs5a", None),
        ("ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3=", None),
        ("ICEiIyQlJicoKSorLC0uLzAxMjM0NTY+", None),
        ("AAAAA", None),
        ("ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3\n", None),
        ("AAECAwQFBgcICQoLDA0ODxAREhMUFRYX", 32),
        (None, None),
    ],
)
def test_vector_5_strict_base64url_rejects(text, length):
    with pytest.raises(ValueError):
        b64u_decode(text, length)


def test_canonical_value_is_accepted():
    assert b64u_encode(b64u_decode("Zk3pR7tQ1xYb9mWc2nLs5Q", 16)) == "Zk3pR7tQ1xYb9mWc2nLs5Q"


# --- helpers: the phone's side of the exchange ---------------------------------------------


def make_request(
    pair_pub: str,
    code: str,
    *,
    ts: int = NOW,
    phone_sk: PrivateKey | None = None,
    nonce: bytes | None = None,
    inner_overrides: dict | None = None,
    data_overrides: dict | None = None,
) -> tuple[dict, bytes, bytes]:
    """Build a pair envelope. Returns (body, shared key, nonce)."""
    phone_sk = phone_sk or PrivateKey.generate()
    nonce = nonce or os.urandom(24)
    shared = Box(phone_sk, PublicKey(b64u_decode(pair_pub, 32))).shared_key()
    data = {
        "code": code,
        "device_name": "Test Phone",
        "platform": "ios",
        "app_version": "1.0.0",
    } | (data_overrides or {})
    inner = {
        "type": "req",
        "ts": ts,
        "method": "POST",
        "path": PAIR,
        "contract": 1,
        "data": data,
    } | (inner_overrides or {})
    plaintext = json.dumps(inner, separators=(",", ":")).encode()
    box = SecretBox(shared).encrypt(plaintext, nonce).ciphertext
    body = {
        "v": 1,
        "nonce": b64u_encode(nonce),
        "ts": ts,
        "phone_pub": b64u_encode(bytes(phone_sk.public_key)),
        "box": b64u_encode(box),
    }
    return body, shared, nonce


def open_reply(response, shared: bytes, nonce: bytes) -> dict:
    """Open an encrypted response and check it answers this request."""
    outer = response.json()
    plain = SecretBox(shared).decrypt(b64u_decode(outer["box"]), b64u_decode(outer["nonce"], 24))
    inner = json.loads(plain)
    assert inner["type"] == "res"
    assert inner["re"] == b64u_encode(nonce)
    assert inner["status"] == response.status_code
    return inner


@pytest.fixture
def app_client(make_client):
    """A phone-side client (no Origin header, like the real app) plus the local dashboard client."""
    dashboard = make_client()
    dashboard.app.state.clock = lambda: NOW
    phone = TestClient(
        dashboard.app, client=("192.168.1.30", 50000), base_url="http://192.168.1.20:8765"
    )
    return dashboard, phone


@pytest.fixture
def start(app_client):
    dashboard, _ = app_client

    def go() -> dict:
        response = dashboard.post("/api/local/pairing")
        assert response.status_code == 200, response.text
        return response.json()

    return go


# --- start pairing --------------------------------------------------------------------------


def test_start_returns_the_qr_payload(app_client, start):
    started = start()
    payload = started["payload"]
    assert set(payload) == {
        "v",
        "app",
        "host",
        "port",
        "code",
        "pair_pub",
        "server_id",
        "name",
        "exp",
    }
    assert payload["v"] == 1 and payload["app"] == "budget-buddy"
    assert payload["host"] == "192.168.1.20" and payload["port"] == 8765
    assert payload["name"] == "Home Base"
    assert payload["exp"] == NOW + 600 and started["seconds_valid"] == 600
    b64u_decode(payload["code"], 16)
    b64u_decode(payload["pair_pub"], 32)
    b64u_decode(payload["server_id"], 16)
    # "Show code as text": the same payload, ready to paste into the phone.
    assert json.loads(started["payload_text"]) == payload
    assert "\n" not in started["payload_text"]


def test_start_response_is_not_cached(app_client):
    dashboard, _ = app_client
    response = dashboard.post("/api/local/pairing")
    assert response.headers["cache-control"] == "no-store"


def test_server_id_is_stable_between_runs(make_client):
    first = make_client().app.state.server_id
    assert make_client().app.state.server_id == first


def test_code_is_stored_only_as_a_hash(app_client, start, data_dir):
    payload = start()["payload"]
    raw = (
        sqlite3.connect(database_path(data_dir))
        .execute("SELECT code_hash, pair_pub, pair_sk FROM pairing_sessions")
        .fetchone()
    )
    assert raw[0] == hashlib.sha256(payload["code"].encode()).hexdigest()
    assert raw[1] == payload["pair_pub"]
    assert isinstance(raw[2], bytes) and raw[2][0] == 1  # encrypted at rest
    database = database_path(data_dir).read_bytes()
    assert payload["code"].encode() not in database


def test_start_is_this_computer_only(make_client):
    lan = make_client("192.168.1.30")
    response = lan.post("/api/local/pairing")
    assert response.status_code == 403 and _error_code(response) == "not_this_computer"


def test_start_needs_a_page_on_this_computer(make_client):
    response = make_client(headers={}).post("/api/local/pairing")
    assert response.status_code == 403 and _error_code(response) == "bad_origin"


def test_start_without_a_home_network(make_client, monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_LAN_IP", "")
    monkeypatch.setattr("app.lan.detect_lan_ip", lambda: None)
    monkeypatch.setattr("app.main.detect_lan_ip", lambda: None)
    response = make_client().post("/api/local/pairing")
    assert response.status_code == 409 and _error_code(response) == "no_home_network"


class FakeServer:
    """Stands in for a uvicorn server: "runs" until told to stop."""

    instances: list = []

    def __init__(self, app, host, port, fail=False):
        self.host, self.port, self.fail = host, port, fail
        self.started = False
        self.should_exit = False
        FakeServer.instances.append(self)

    def run(self):
        if self.fail:
            return
        self.started = True
        while not self.should_exit:
            time.sleep(0.01)


@pytest.fixture
def lan_listener(make_client):
    """A client whose app can open its (fake) home-network listener."""
    FakeServer.instances = []

    def make(fail=False):
        client = make_client()
        client.app.state.clock = lambda: NOW
        listener = client.app.state.listener
        listener._make_server = lambda app, host, port: FakeServer(app, host, port, fail)
        listener.attach()
        return client, listener

    return make


def test_first_pairing_opens_the_listener_on_the_specific_lan_address(lan_listener):
    client, listener = lan_listener()
    assert not listener.reachable()  # nothing wanted yet: this computer only
    body = client.post("/api/local/pairing").json()
    assert body["phone_can_connect"] is True and body["message"] is None
    assert [(f.host, f.port) for f in FakeServer.instances] == [("192.168.1.20", 8765)]
    assert listener.bound_ip == "192.168.1.20"
    listener.close()


def test_listener_stays_while_a_phone_is_paired_and_closes_when_nothing_needs_it(lan_listener):
    client, listener = lan_listener()
    qr = client.post("/api/local/pairing").json()["payload"]
    phone = TestClient(
        client.app, client=("192.168.1.30", 50000), base_url="http://192.168.1.20:8765"
    )
    response, shared, nonce = pair_once(phone, qr)
    device_id = open_reply(response, shared, nonce)["data"]["device_id"]
    client.get("/api/local/devices")
    assert listener.running  # a phone is paired
    client.post(f"/api/local/devices/{device_id}/revoke")
    assert not listener.running and listener.bound_ip is None  # no session, no active phone


def test_listener_closes_when_the_pairing_expires_unused(lan_listener):
    client, listener = lan_listener()
    client.post("/api/local/pairing")
    assert listener.running
    client.app.state.clock = lambda: NOW + 601
    client.get("/api/local/devices")
    assert not listener.running


def test_listener_is_wanted_on_start_when_a_phone_is_already_paired(
    app_client, start, lan_listener
):
    dashboard, phone = app_client
    pair_once(phone, start()["payload"])
    listener = dashboard.app.state.listener
    listener._make_server = lambda app, host, port: FakeServer(app, host, port)
    listener.attach()
    listener.sync_from_database()
    assert listener.running
    listener.close()


def test_phone_cant_connect_when_the_listener_fails(lan_listener):
    client, listener = lan_listener(fail=True)
    body = client.post("/api/local/pairing").json()
    assert body["phone_can_connect"] is False
    assert "home-network connection" in body["message"]


def test_phone_cant_connect_when_nobody_runs_the_listener(make_client):
    body = make_client().post("/api/local/pairing").json()  # never attached, like a test run
    assert body["phone_can_connect"] is False and body["message"]


def test_explicit_loopback_host_means_never_the_network(monkeypatch, lan_listener):
    monkeypatch.setenv("BUDGET_BUDDY_HOST", "127.0.0.1")
    client, listener = lan_listener()
    body = client.post("/api/local/pairing").json()
    assert body["phone_can_connect"] is False
    assert "only on this computer" in body["message"]
    assert FakeServer.instances == []


def test_explicit_network_host_is_reachable_without_a_second_listener(monkeypatch, lan_listener):
    monkeypatch.setenv("BUDGET_BUDDY_HOST", "0.0.0.0")
    client, _ = lan_listener()
    assert client.post("/api/local/pairing").json()["phone_can_connect"] is True
    assert FakeServer.instances == []


def test_default_host_is_not_treated_as_explicit(make_client):
    assert "host" not in make_client().app.state.settings.model_fields_set


def test_deeply_nested_json_is_a_plain_400(app_client, start):
    _, phone = app_client
    start()
    body = b"[" * 8000 + b"]" * 8000
    response = phone.post(
        PAIR, content=body, headers=LAN_HOST | {"Content-Type": "application/json"}
    )
    assert response.status_code == 400 and _error_code(response) == "bad_request"


def test_old_session_keys_are_erased_at_startup_and_when_listing_devices(
    app_client, start, make_client
):
    dashboard, _ = app_client
    start()
    dashboard.app.state.clock = lambda: NOW + 601

    def key_left():
        with Session(dashboard.app.state.engine) as session:
            return session.scalars(select(PairingSession.pair_sk)).one()

    assert key_left() is not None
    dashboard.get("/api/local/devices")
    assert key_left() is None

    start_app = make_client()
    start_app.app.state.clock = lambda: NOW
    start_app.post("/api/local/pairing")
    start_app.app.state.clock = lambda: NOW + 601
    with start_app:  # runs the app's startup
        pass
    with Session(start_app.app.state.engine) as session:
        assert all(k is None for k in session.scalars(select(PairingSession.pair_sk)))


def test_settings_reject_a_public_lan_ip(monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_LAN_IP", "8.8.8.8")
    with pytest.raises(ValueError):
        Settings()


# --- POST /api/pair: the contract's vector 4 ------------------------------------------------

PAIR_SK = bytes(range(0xA0, 0xC0))
VECTOR_CODE = "pQ3mX9vT2aLk8RzN1bWc4g"
VECTOR_PHONE_PUB = "ST6C_HRGSlkmiBdiPSBTxeuOLMSpiLT-4XnsawENUx0"
VECTOR_BODY = {
    "v": 1,
    "nonce": "wMHCw8TFxsfIycrLzM3Oz9DR0tPU1dbX",
    "ts": 1790000000,
    "phone_pub": VECTOR_PHONE_PUB,
    "box": (
        "iX68iqmvSCofJGxoNa6ebGX424xYOa65Hp175w4pshg0QFxkfGk7IJSqHtBmtUmvZqsuM3uzkXYBVTevNr3Pt8LZmisOoF1RHF7b"
        "cQ1d01XIRobOmjXEr5AKOoJ9Gip52s6weSGEDbLZYnq9dE0HaO4Hb475qcwAQ_hrx_EpnEXBfJatjlr-W3-1-1XYBTtN9dOC9U12"
        "WfqBH76uDT23FI_1BTze3vUIbT3lBerNaXkQflETufHrnpuhaIUEeVvJzNi_A-2QmCAH"
    ),
}


def test_contract_vector_4_pairs_and_the_reply_opens_with_shared(app_client):
    dashboard, phone = app_client
    with Session(dashboard.app.state.engine) as session:
        session.add(
            PairingSession(
                code_hash=hashlib.sha256(VECTOR_CODE.encode()).hexdigest(),
                pair_pub="YFpyXSpK3-6xop4X7dYhwbdZPujNvESsbEq24vgF0jw",
                pair_sk=b64u_encode(PAIR_SK),
                created_at=NOW,
                exp=NOW + 600,
            )
        )
        session.commit()

    response = phone.post(PAIR, json=VECTOR_BODY, headers=LAN_HOST)
    assert response.status_code == 200, response.text
    shared = b64u_decode("zSsDtyenL7oJQc53ndiVIG5KaKRYVTL4LHpaOqazn_c", 32)
    reply = open_reply(response, shared, b64u_decode(VECTOR_BODY["nonce"], 24))
    data = reply["data"]
    assert data["device_id"] == 1
    assert data["server_id"] == dashboard.app.state.server_id
    assert data["server_name"] == "Home Base"
    b64u_decode(data["token"], 32)
    b64u_decode(data["sync_key"], 32)
    assert reply["ts"] == NOW

    with Session(dashboard.app.state.engine) as session:
        device = session.scalars(select(Device)).one()
        assert device.name == "Test Phone" and device.platform == "ios"
        assert device.app_version == "1.0.0" and not device.revoked
        # Only the hash of the token is stored; the sync key is the encrypted column.
        assert device.token_hash == hashlib.sha256(data["token"].encode("ascii")).hexdigest()
        assert device.sync_key == data["sync_key"]
        ended = session.scalars(select(PairingSession)).one()
        assert ended.used_at == NOW and ended.pair_sk is None  # private key erased


def test_token_hash_vector():
    token = "YGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6e3x9fn8"
    assert device_service.hash_token(token) == (
        "128a42f0efc787b4710881a27873ead95dfcf13a9dfbdf9ca1f2f0600ecb9407"
    )


# --- POST /api/pair: normal flow and its edges -----------------------------------------------


def pair_once(phone, qr, **kwargs):
    body, shared, nonce = make_request(qr["pair_pub"], qr["code"], **kwargs)
    return phone.post(PAIR, json=body, headers=LAN_HOST), shared, nonce


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
    assert second.status_code == 410 and _error_code(second) == "pairing_expired"


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
    assert _error_code(pair_once(phone, old)[0]) == "decrypt_failed"  # old key is gone
    assert pair_once(phone, new)[0].status_code == 200


def test_expired_code(app_client, start):
    dashboard, phone = app_client
    qr = start()["payload"]
    dashboard.app.state.clock = lambda: NOW + 601
    response = pair_once(phone, qr, ts=NOW + 601)[0]
    assert response.status_code == 410 and _error_code(response) == "pairing_expired"
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
    assert response.status_code == 410 and _error_code(response) == "pairing_expired"
    with Session(dashboard.app.state.engine) as session:
        assert session.scalars(select(Device)).all() == []


def test_garbage_does_not_count_against_the_user(app_client, start):
    _, phone = app_client
    qr = start()["payload"]
    for _ in range(6):
        body, _, _ = make_request(qr["pair_pub"], qr["code"])
        body["box"] = b64u_encode(os.urandom(80))  # can't be opened
        response = phone.post(PAIR, json=body, headers=LAN_HOST)
        assert response.status_code == 401 and _error_code(response) == "decrypt_failed"
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
    assert response.status_code == 410 and _error_code(response) == "pairing_expired"


@pytest.mark.parametrize("skew", [301, -301])
def test_clock_skew_is_plain_and_has_server_time(app_client, start, skew):
    _, phone = app_client
    qr = start()["payload"]
    response = pair_once(phone, qr, ts=NOW + skew)[0]
    assert response.status_code == 400 and _error_code(response) == "clock_skew"
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
    assert response.status_code == 401 and _error_code(response) == "decrypt_failed"


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
    assert response.status_code == 401 and _error_code(response) == "decrypt_failed"


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
    assert response.status_code == 400 and _error_code(response) == "bad_request"


def test_missing_envelope_fields_and_non_json(app_client, start):
    _, phone = app_client
    start()
    assert phone.post(PAIR, json={}, headers=LAN_HOST).status_code == 400
    assert phone.post(PAIR, json=[1], headers=LAN_HOST).status_code == 400
    bad = phone.post(
        PAIR, content=b"{nope", headers=LAN_HOST | {"Content-Type": "application/json"}
    )
    assert bad.status_code == 400 and _error_code(bad) == "bad_request"
    wrong_type = phone.post(PAIR, content=b"{}", headers=LAN_HOST | {"Content-Type": "text/plain"})
    assert wrong_type.status_code == 400 and _error_code(wrong_type) == "bad_request"


def test_body_over_16_kib_is_refused_while_streaming(app_client, start):
    _, phone = app_client
    start()
    headers = LAN_HOST | {"Content-Type": "application/json"}

    def chunks():  # no Content-Length: chunked upload
        for _ in range(20):
            yield b" " * 1024

    response = phone.post(PAIR, content=chunks(), headers=headers)
    assert response.status_code == 413 and _error_code(response) == "too_large"
    big = phone.post(PAIR, content=b" " * (16 * 1024 + 1), headers=headers)
    assert big.status_code == 413


def test_rate_limit_is_ten_a_minute_per_address(app_client, start):
    dashboard, phone = app_client
    start()
    for _ in range(10):
        assert phone.post(PAIR, json={}, headers=LAN_HOST).status_code == 400
    response = phone.post(PAIR, json={}, headers=LAN_HOST)
    assert response.status_code == 429 and _error_code(response) == "too_many_attempts"
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
    assert bad.status_code == 403 and _error_code(bad) == "bad_host"
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


# --- devices: list and remove ----------------------------------------------------------------


def _pair(phone, start, name="Test Phone"):
    qr = start()["payload"]
    response, shared, nonce = pair_once(phone, qr, data_overrides={"device_name": name})
    return open_reply(response, shared, nonce)["data"]


def test_revoked_token_stops_working_at_once(app_client, start):
    dashboard, phone = app_client
    data = _pair(phone, start)
    response = dashboard.post(f"/api/local/devices/{data['device_id']}/revoke")
    assert response.status_code == 200
    assert response.json()["revoked"] is True and response.json()["revoked_at"]

    with Session(dashboard.app.state.engine) as session:
        with pytest.raises(Exception) as caught:
            device_service.authenticate_token(session, data["token"])
        assert (caught.value.status, caught.value.code) == (401, "device_revoked")
        device = session.get(Device, data["device_id"])
        assert device.sync_key is None  # the key is deleted, the row stays
    # Listed with history, and removing twice is harmless.
    assert dashboard.get("/api/local/devices").json()[0]["revoked"] is True
    assert dashboard.post(f"/api/local/devices/{data['device_id']}/revoke").status_code == 200


def test_unknown_and_malformed_tokens(app_client):
    dashboard, _ = app_client
    with Session(dashboard.app.state.engine) as session:
        for token, status, code in [
            (b64u_encode(os.urandom(32)), 401, "not_paired"),
            ("not a token", 400, "bad_request"),
            (None, 400, "bad_request"),
        ]:
            with pytest.raises(Exception) as caught:
                device_service.authenticate_token(session, token)
            assert (caught.value.status, caught.value.code) == (status, code)


def test_revoking_one_phone_leaves_the_other(app_client, start):
    dashboard, phone = app_client
    first = _pair(phone, start, "First")
    second = _pair(phone, start, "Second")
    dashboard.post(f"/api/local/devices/{first['device_id']}/revoke")
    listed = {d["name"]: d["revoked"] for d in dashboard.get("/api/local/devices").json()}
    assert listed == {"First": True, "Second": False}
    with Session(dashboard.app.state.engine) as session:
        assert device_service.authenticate_token(session, second["token"]).name == "Second"


def test_revoke_unknown_device_is_a_plain_404(app_client):
    dashboard, _ = app_client
    response = dashboard.post("/api/local/devices/99/revoke")
    assert response.status_code == 404 and _error_code(response) == "not_found"


def test_device_routes_are_this_computer_only(make_client):
    lan = make_client("192.168.1.30")
    assert lan.get("/api/local/devices").status_code == 403
    assert lan.post("/api/local/devices/1/revoke").status_code == 403


def test_paired_phone_is_noticed_without_refreshing_settings(app_client, start):
    dashboard, phone = app_client
    assert dashboard.get("/api/local/devices").json() == []
    _pair(phone, start, "Ana's iPhone")
    assert [d["name"] for d in dashboard.get("/api/local/devices").json()] == ["Ana's iPhone"]


def test_health_reports_contract(client):
    assert client.get("/api/health").json()["contract"] == 1


def _free_port() -> int:
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_real_listener_stops_and_restarts_quickly_without_running_the_app_lifespan(
    make_client, monkeypatch
):
    port = _free_port()
    monkeypatch.setenv("BUDGET_BUDDY_PORT", str(port))
    client = make_client(base_url=f"http://127.0.0.1:{port}")
    listener = client.app.state.listener
    listener.attach()
    closed = []
    original_close = listener.close
    listener.close = lambda: (closed.append(1), original_close())  # app shutdown calls this
    started = time.monotonic()
    for _ in range(2):  # open, close, open again
        listener.sync(True, "127.0.0.1")
        assert listener.running
        listener.sync(False, "127.0.0.1")
        assert not listener.running
    assert time.monotonic() - started < 4  # no 5 second wait on a lock
    assert closed == []  # the second listener never ran the app's shutdown
    with Session(client.app.state.engine) as session:  # shared database is still open
        assert session.scalars(select(Device)).all() == []


@pytest.mark.parametrize("host", ["localhost", "LocalHost", "LOCALHOST.", "::1", "127.0.0.2"])
def test_explicit_loopback_names_count_as_never(monkeypatch, lan_listener, host):
    monkeypatch.setenv("BUDGET_BUDDY_HOST", host)
    _, listener = lan_listener()
    assert listener.never and not listener.main_is_on_network
