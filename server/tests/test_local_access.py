"""Sync contract §3.1 access rules: Host allowlist. Fake data only."""

import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

ACCOUNTS = "/api/local/accounts"


def _error_code(response) -> str:
    return response.json()["error"]["code"]


# --- H1: Host allowlist (stops DNS rebinding) ---


@pytest.mark.parametrize(
    "host", ["127.0.0.1:8765", "localhost:8765", "[::1]:8765", "LocalHost:8765"]
)
def test_allowed_hosts(client, host):
    assert client.get("/api/health", headers={"Host": host}).status_code == 200
    assert client.get(ACCOUNTS, headers={"Host": host}).status_code == 200


@pytest.mark.parametrize(
    "host",
    [
        "attacker.example:8765",  # a DNS-rebinding page
        "attacker.example",
        "127.0.0.1:9999",  # right host, wrong port
        "localhost:80",
        "127.0.0.1",  # no port
        "localhost",
        "192.168.1.20:8765",  # LAN address isn't allowed until pairing ships
        "127.0.0.1:8765.attacker.example",
        "",
    ],
)
def test_foreign_host_is_refused(client, host):
    for method, path in [("get", "/api/health"), ("get", ACCOUNTS), ("post", ACCOUNTS)]:
        response = client.request(method, path, headers={"Host": host}, json={"name": "X"})
        assert response.status_code == 403, (method, path)
        assert _error_code(response) == "bad_host"


def test_rebinding_page_cannot_read_or_write(client, make_account):
    make_account()
    rebinding = {"Host": "attacker.example:8765", "Origin": "http://attacker.example:8765"}
    response = client.get(ACCOUNTS, headers=rebinding)
    assert response.status_code == 403
    assert "Test Checking" not in response.text
    created = client.post(ACCOUNTS, headers=rebinding, json={"name": "Evil", "kind": "checking"})
    assert created.status_code == 403
    assert [a["name"] for a in client.get(ACCOUNTS).json()] == ["Test Checking"]


def _raw_request(app, headers: list[tuple[bytes, bytes]]) -> tuple[int, bytes]:
    """Send one request straight to the ASGI app, with exactly the headers given."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/health",
        "raw_path": b"/api/health",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8765),
    }
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body


def test_missing_or_repeated_host_is_refused(client):
    assert _raw_request(client.app, [(b"host", b"127.0.0.1:8765")])[0] == 200
    status, body = _raw_request(client.app, [])
    assert (status, b"bad_host" in body) == (403, True)
    twice = [(b"host", b"127.0.0.1:8765"), (b"host", b"attacker.example:8765")]
    assert _raw_request(client.app, twice)[0] == 403


def test_host_follows_configured_port(make_client, monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_PORT", "9000")
    client = make_client(base_url="http://localhost:9000")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health", headers={"Host": "localhost:8765"}).status_code == 403


def test_websocket_with_foreign_host_is_closed(client):
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("ws://attacker.example:8765/api/health"):
            pass
    assert excinfo.value.code == 1008
