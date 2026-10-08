"""The phone's side of pairing and sync, for the sync tests. Fake data only.

Builds requests exactly as sync contract section 4 describes, so the tests exercise the real
envelope rules (not a shortcut around them).
"""

import json
import os

from fastapi.testclient import TestClient
from nacl.public import Box, PrivateKey, PublicKey
from nacl.secret import SecretBox

from app.crypto.b64url import b64u_decode, b64u_encode

NOW = 1790000000
LAN_BASE = "http://192.168.1.20:8765"
LAN_PEER = ("192.168.1.30", 50000)


def pair_phone(dashboard: TestClient, name: str = "Test Phone") -> "Phone":
    """Pair a fake phone through the real flow and return it, ready to sync."""
    dashboard.app.state.clock = lambda: NOW
    started = dashboard.post("/api/local/pairing").json()["payload"]
    phone_sk = PrivateKey.generate()
    shared = Box(phone_sk, PublicKey(b64u_decode(started["pair_pub"], 32))).shared_key()
    nonce = os.urandom(24)
    inner = {
        "type": "req",
        "ts": NOW,
        "method": "POST",
        "path": "/api/pair",
        "contract": 1,
        "data": {
            "code": started["code"],
            "device_name": name,
            "platform": "ios",
            "app_version": "1.0.0",
        },
    }
    box = SecretBox(shared).encrypt(json.dumps(inner).encode(), nonce).ciphertext
    body = {
        "v": 1,
        "nonce": b64u_encode(nonce),
        "ts": NOW,
        "phone_pub": b64u_encode(bytes(phone_sk.public_key)),
        "box": b64u_encode(box),
    }
    http = TestClient(dashboard.app, client=LAN_PEER, base_url=LAN_BASE)
    response = http.post("/api/pair", json=body)
    assert response.status_code == 200, response.text
    outer = response.json()
    plain = SecretBox(shared).decrypt(b64u_decode(outer["box"]), b64u_decode(outer["nonce"], 24))
    data = json.loads(plain)["data"]
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
        outer = response.json()
        plain = SecretBox(self.key).decrypt(
            b64u_decode(outer["box"]), b64u_decode(outer["nonce"], 24)
        )
        inner = json.loads(plain)
        assert inner["type"] == "res" and inner["re"] == b64u_encode(nonce)
        assert inner["status"] == response.status_code
        return inner

    def ok(self, path: str, data: dict | None = None, **kwargs) -> dict:
        response, nonce = self.call(path, data, **kwargs)
        assert response.status_code == 200, response.text
        return self.open(response, nonce)["data"]
