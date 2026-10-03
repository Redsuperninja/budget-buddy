import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.network import is_private_address


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.1.20",
        "169.254.10.10",
        "::1",
        "fd12:3456:789a::1",
        "fe80::1",
        "fe80::1%eth0",
        "::ffff:192.168.1.20",
    ],
)
def test_private_addresses_allowed(host):
    assert is_private_address(host)


@pytest.mark.parametrize(
    "host",
    [
        "8.8.8.8",
        "172.32.0.1",
        "100.64.0.1",
        "2001:4860:4860::8888",
        "::ffff:8.8.8.8",
        "0.0.0.0",
        "testclient",
        "",
        None,
    ],
)
def test_public_or_invalid_addresses_rejected(host):
    assert not is_private_address(host)


def test_middleware_allows_lan_client(make_client):
    client = make_client("192.168.1.50")
    assert client.get("/api/health").status_code == 200


def test_middleware_rejects_public_client(make_client):
    client = make_client("203.0.113.7")
    response = client.get("/api/health")
    assert response.status_code == 403
    assert "home network" in response.json()["detail"]


# TestClient.websocket_connect ignores base_url, so give it the full address.
WS_BASE = "ws://127.0.0.1:8765"
LAN_WS = "/api/sync/test-ws"  # under a route group the phone may use
LOCAL_WS = "/test-ws"  # anywhere else: this computer only


def _client_with_test_websockets(make_client, peer: str) -> TestClient:
    """The real app plus test-only WebSocket echo routes (not part of the shipped app)."""
    client = make_client(peer)

    async def echo(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text(await websocket.receive_text())
        await websocket.close()

    client.app.add_api_websocket_route(LAN_WS, echo)
    client.app.add_api_websocket_route(LOCAL_WS, echo)
    return client


@pytest.mark.parametrize(
    ("peer", "path"),
    [("192.168.1.50", LAN_WS), ("127.0.0.1", LAN_WS), ("127.0.0.1", LOCAL_WS)],
)
def test_websocket_allowed(make_client, peer, path):
    client = _client_with_test_websockets(make_client, peer)
    with client.websocket_connect(WS_BASE + path) as ws:
        ws.send_text("hi")
        assert ws.receive_text() == "hi"


@pytest.mark.parametrize(
    ("peer", "path"),
    [("203.0.113.7", LAN_WS), ("203.0.113.7", LOCAL_WS), ("192.168.1.50", LOCAL_WS)],
)
def test_websocket_rejected(make_client, peer, path):
    client = _client_with_test_websockets(make_client, peer)
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(WS_BASE + path):
            pass
    assert excinfo.value.code == 1008


def test_lifespan_passes_through(make_client):
    # Lifespan events have no client address; the middleware must let them through.
    with make_client("203.0.113.7") as client:
        assert client.get("/api/health").status_code == 403
