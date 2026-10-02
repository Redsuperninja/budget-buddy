import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
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


def test_middleware_allows_lan_client(data_dir):
    client = TestClient(create_app(), client=("192.168.1.50", 50000))
    assert client.get("/api/health").status_code == 200


def test_middleware_rejects_public_client(data_dir):
    client = TestClient(create_app(), client=("203.0.113.7", 50000))
    response = client.get("/api/health")
    assert response.status_code == 403
    assert "home network" in response.json()["detail"]


def _app_with_test_websocket():
    """The real app plus a test-only WebSocket echo route (not part of the shipped app)."""
    app = create_app()

    @app.websocket("/test-ws")
    async def echo(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text(await websocket.receive_text())
        await websocket.close()

    return app


def test_websocket_allowed_from_lan_client(data_dir):
    client = TestClient(_app_with_test_websocket(), client=("192.168.1.50", 50000))
    with client.websocket_connect("/test-ws") as ws:
        ws.send_text("hi")
        assert ws.receive_text() == "hi"


def test_websocket_rejected_from_public_client(data_dir):
    client = TestClient(_app_with_test_websocket(), client=("203.0.113.7", 50000))
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/test-ws"):
            pass
    assert excinfo.value.code == 1008


def test_lifespan_passes_through(data_dir):
    # Lifespan events have no client address; the middleware must let them through.
    with TestClient(create_app(), client=("203.0.113.7", 50000)) as client:
        assert client.get("/api/health").status_code == 403
