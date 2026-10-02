import pytest
from fastapi.testclient import TestClient

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
