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
WS_URL = "ws://127.0.0.1:8765/test-ws"


def _client_with_test_websocket(make_client, peer: str) -> TestClient:
    """The real app plus a test-only WebSocket echo route (not part of the shipped app)."""
    client = make_client(peer)

    @client.app.websocket("/test-ws")
    async def echo(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text(await websocket.receive_text())
        await websocket.close()

    return client


def test_websocket_allowed_from_lan_client(make_client):
    client = _client_with_test_websocket(make_client, "192.168.1.50")
    with client.websocket_connect(WS_URL) as ws:
        ws.send_text("hi")
        assert ws.receive_text() == "hi"


def test_websocket_rejected_from_public_client(make_client):
    client = _client_with_test_websocket(make_client, "203.0.113.7")
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(WS_URL):
            pass
    assert excinfo.value.code == 1008


def test_lifespan_passes_through(make_client):
    # Lifespan events have no client address; the middleware must let them through.
    with make_client("203.0.113.7") as client:
        assert client.get("/api/health").status_code == 403
