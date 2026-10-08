"""The phone's side of pairing and sync, shared by the pairing and sync tests. Fake data only.

Builds requests exactly as sync contract section 4 describes, so the tests exercise the real
envelope rules (not a shortcut around them). The example address is a private one
(192.168.1.20) set up in conftest.
"""

import json
import os

from fastapi.testclient import TestClient
from nacl.public import Box, PrivateKey, PublicKey
from nacl.secret import SecretBox
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_decode, b64u_encode
from app.models import SeenNonce

NOW = 1790000000
PAIR = "/api/pair"
SNAPSHOT = "/api/sync/snapshot"
ACK = "/api/sync/ack"
LAN_BASE = "http://192.168.1.20:8765"
LAN_HOST = {"Host": "192.168.1.20:8765"}
LAN_PEER = ("192.168.1.30", 50000)


def error_code(response) -> str:
    return response.json()["error"]["code"]


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


def lan_client(app) -> TestClient:
    """A phone-side client (no Origin header, like the real app) on the home network."""
    return TestClient(app, client=LAN_PEER, base_url=LAN_BASE)


def pair_once(phone, qr, **kwargs):
    """Send one pairing request for ``qr``. Returns (response, shared key, nonce)."""
    body, shared, nonce = make_request(qr["pair_pub"], qr["code"], **kwargs)
    return phone.post(PAIR, json=body, headers=LAN_HOST), shared, nonce


def pair_named(phone, start, name="Test Phone") -> dict:
    """Start pairing and complete it as ``name``. Returns the reply's data."""
    response, shared, nonce = pair_once(
        phone, start()["payload"], data_overrides={"device_name": name}
    )
    return open_reply(response, shared, nonce)["data"]


def pair_phone(dashboard: TestClient, name: str = "Test Phone") -> "Phone":
    """Pair a fake phone through the real flow and return it, ready to sync."""
    dashboard.app.state.clock = lambda: NOW
    started = dashboard.post("/api/local/pairing").json()["payload"]
    http = lan_client(dashboard.app)
    response, shared, nonce = pair_once(http, started, data_overrides={"device_name": name})
    assert response.status_code == 200, response.text
    data = open_reply(response, shared, nonce)["data"]
    return Phone(dashboard, http, data["token"], data["sync_key"], data["device_id"])


class Phone:
    def __init__(self, dashboard, http, token: str, sync_key: str, device_id: int) -> None:
        self.dashboard = dashboard
        self.http = http
        self.token = token
        self.key = b64u_decode(sync_key, 32)
        self.device_id = device_id

    def envelope(
        self,
        path: str,
        data: dict | None = None,
        *,
        ts: int = NOW,
        nonce: bytes | None = None,
        key: bytes | None = None,
        inner: dict | None = None,
    ) -> tuple[dict, bytes]:
        nonce = nonce or os.urandom(24)
        message = {
            "type": "req",
            "ts": ts,
            "method": "POST",
            "path": path,
            "contract": 1,
            "data": {} if data is None else data,
        } | (inner or {})
        plaintext = json.dumps(message, separators=(",", ":")).encode()
        box = SecretBox(key or self.key).encrypt(plaintext, nonce).ciphertext
        return {"v": 1, "nonce": b64u_encode(nonce), "ts": ts, "box": b64u_encode(box)}, nonce

    def call(
        self,
        path: str,
        data: dict | None = None,
        *,
        token: str | None = "default",
        body: bytes | dict | None = None,
        headers: dict | None = None,
        **kwargs,
    ):
        """POST to ``path``. Returns ``(response, request nonce)``."""
        sent, nonce = self.envelope(path, data, **kwargs)
        head = {"Content-Type": "application/json"} | (headers or {})
        if token == "default":
            token = self.token
        if token is not None:
            head["Authorization"] = f"Bearer {token}"
        if body is None:
            body = sent
        content = body if isinstance(body, bytes) else json.dumps(body).encode()
        return self.http.post(path, content=content, headers=head), nonce

    def open(self, response, nonce: bytes) -> dict:
        """Open an encrypted reply and check it answers this request (section 4.3)."""
        return open_reply(response, self.key, nonce)

    def ok(self, path: str, data: dict | None = None, **kwargs) -> dict:
        response, nonce = self.call(path, data, **kwargs)
        assert response.status_code == 200, response.text
        return self.open(response, nonce)["data"]


def seen_nonce_count(phone: Phone) -> int:
    with Session(phone.dashboard.app.state.engine) as session:
        return len(session.scalars(select(SeenNonce)).all())
