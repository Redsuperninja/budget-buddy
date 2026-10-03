"""Sync contract §3.1 access rules: Host allowlist, Origin on writes. Fake data only."""

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


@pytest.mark.parametrize("path", ["/api/pair", "/api/sync/ack"])
def test_phone_routes_do_not_need_an_origin(make_client, path):
    # The phone app isn't a browser and sends no Origin. These routes don't exist yet (#14/#15),
    # so a 404 shows the request got past the Origin check.
    response = make_client(headers={}).post(path, json={})
    assert response.status_code == 404
