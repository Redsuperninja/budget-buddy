"""Sync contract §3.1 access rules: Host allowlist, Origin on writes, and this-computer-only by
default. Fake data only."""

import asyncio
import re

import pytest
from fastapi import APIRouter
from starlette.routing import Mount, WebSocketRoute
from starlette.websockets import WebSocketDisconnect

from app.network import is_lan_route

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
        "192.168.1.21:8765",  # not this computer's own home-network address
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


# --- M1: Origin check on anything that changes data (stops cross-site requests) ---


def _writes(account_id: int) -> list[tuple[str, str, dict | None]]:
    return [
        ("post", ACCOUNTS, {"name": "X", "kind": "checking"}),
        ("patch", f"{ACCOUNTS}/{account_id}", {"name": "Y"}),
        ("delete", f"{ACCOUNTS}/{account_id}", None),
        ("post", "/api/local/transactions", {"account_id": account_id, "amount_cents": 1}),
    ]


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "http://attacker.example",
        "http://attacker.example:8765",
        "http://127.0.0.1:9999",
        "https://127.0.0.1:8765",
        "http://127.0.0.1:8765.attacker.example",
        "null",  # sandboxed iframes and some redirects
        "",
    ],
)
def test_write_without_matching_origin_is_refused(make_client, make_account, origin):
    account_id = make_account()["id"]
    headers = {} if origin is None else {"Origin": origin}
    client = make_client(headers=headers)
    for method, path, body in _writes(account_id):
        response = client.request(method, path, json=body)
        assert response.status_code == 403, (method, path)
        assert _error_code(response) == "bad_origin"
    assert client.get(f"{ACCOUNTS}/{account_id}").json()["name"] == "Test Checking"


@pytest.mark.parametrize(
    "origin", ["http://127.0.0.1:8765", "http://localhost:8765", "http://[::1]:8765"]
)
def test_write_from_this_computer_is_allowed(make_client, origin):
    client = make_client(headers={"Origin": origin})
    response = client.post(ACCOUNTS, json={"name": "X", "kind": "checking"})
    assert response.status_code == 201, response.text


def test_reads_do_not_need_an_origin(make_client):
    client = make_client(headers={})
    assert client.get(ACCOUNTS).status_code == 200
    assert client.head("/api/health").status_code != 403


def test_cross_site_form_post_does_not_succeed(make_client):
    # What an HTML form on another site can send: text/plain, no matching Origin.
    form = {"Content-Type": "text/plain"}
    body = '{"name": "X", "kind": "checking"}'
    no_origin = make_client(headers={})
    assert no_origin.post(ACCOUNTS, content=body, headers=form).status_code == 403
    foreign = make_client(headers={"Origin": "http://attacker.example"})
    assert foreign.post(ACCOUNTS, content=body, headers=form).status_code == 403
    # Even from this computer, a non-JSON body is not accepted.
    assert make_client().post(ACCOUNTS, content=body, headers=form).status_code == 422
    assert make_client().get(ACCOUNTS).json() == []


def test_phone_routes_do_not_need_an_origin(make_client):
    # The phone app isn't a browser and sends no Origin. /api/sync/* doesn't exist yet (#15), so
    # a 404 shows the request got past the Origin check; /api/pair answers (no QR code is active).
    client = make_client(headers={})
    assert client.post("/api/sync/ack", json={}).status_code == 404
    response = client.post("/api/pair", json={})
    assert response.status_code == 410
    assert _error_code(response) == "pairing_expired"


# --- M2: this computer only, unless the route is one of the phone's ---

LAN_PEERS = ["192.168.1.20", "10.0.0.5", "fe80::1", "::ffff:192.168.1.20"]


def _concrete(path: str) -> str:
    return re.sub(r"{[^}]+}", "1", path)


def _walk(routes) -> list[tuple[str, str]]:
    found = []
    for route in routes:
        if hasattr(route, "effective_candidates"):  # an included router (FastAPI >= 0.140)
            found += _walk(route.effective_candidates())
        elif isinstance(route, Mount):
            raise AssertionError(f"walk doesn't look inside mounts yet: {route.path}")
        elif isinstance(route, WebSocketRoute):
            continue  # covered by the WebSocket tests in test_network.py
        else:
            methods = sorted(route.methods or ["GET"])
            found += [(method, _concrete(route.path)) for method in methods]
    return found


def _http_routes(app) -> list[tuple[str, str]]:
    """Every (method, path) the app serves, with path parameters filled in."""
    return _walk(app.routes)


@pytest.mark.parametrize("peer", LAN_PEERS)
def test_every_route_but_the_phones_refuses_the_home_network(make_client, monkeypatch, peer):
    monkeypatch.setenv("BUDGET_BUDDY_DEV_MODE", "true")  # include /docs and /openapi.json
    lan = make_client(peer)
    routes = _http_routes(lan.app)
    assert ("POST", "/api/local/transactions/1/transfer") in routes  # the walk sees everything
    assert ("GET", "/openapi.json") in routes

    lan_facing = sorted({path for _, path in routes if is_lan_route(path)})
    assert lan_facing == ["/api/health", "/api/pair"]  # /api/sync/* arrives with #15

    for method, path in routes:
        response = lan.request(method, path, json={})
        if is_lan_route(path):
            assert response.status_code != 403, (method, path)  # "/api/pair" says 410/400, not 403
        else:
            assert response.status_code == 403, (method, path)
            if method != "HEAD":  # HEAD answers have no body
                assert _error_code(response) == "not_this_computer", (method, path)


def test_new_router_is_this_computer_only_without_any_setup(make_client):
    lan = make_client("192.168.1.20")
    loopback = make_client()
    for client in (lan, loopback):
        router = APIRouter(prefix="/api/local/new-thing")  # no dependencies on purpose
        router.add_api_route("", lambda: {"ok": True}, methods=["GET"])
        client.app.include_router(router)
    assert lan.get("/api/local/new-thing").status_code == 403
    assert loopback.get("/api/local/new-thing").json() == {"ok": True}


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/health", True),
        ("/api/pair", True),
        ("/api/sync/snapshot", True),
        ("/api/sync/", True),
        ("/api/sync", False),
        ("/api/syncx/snapshot", False),
        ("/api/health/", False),
        ("/api/healthz", False),
        ("/api/pair/qr", False),
        ("/api/local/accounts", False),
        ("/docs", False),
        ("/", False),
    ],
)
def test_is_lan_route(path, expected):
    assert is_lan_route(path) is expected


def test_wrong_network_answer_comes_before_origin_answer(make_client):
    # A LAN device is told "this computer only", not something about Origin.
    response = make_client("192.168.1.20", headers={}).post(ACCOUNTS, json={})
    assert _error_code(response) == "not_this_computer"
