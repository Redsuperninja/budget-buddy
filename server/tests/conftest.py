from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(autouse=True)
def memory_key_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep encryption keys in memory: tests must never touch the real OS password vault."""
    monkeypatch.setenv("BUDGET_BUDDY_KEY_STORE", "memory")
    monkeypatch.setenv("BUDGET_BUDDY_INSECURE_TEST_KEYSTORE", "1")


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway data folder so tests never touch real user data."""
    path = tmp_path / "bb-data"
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(path))
    monkeypatch.delenv("BUDGET_BUDDY_PORT", raising=False)
    return path


# What a browser on this computer sends when it opens the Home Base at its default address.
BASE_URL = "http://127.0.0.1:8765"


@pytest.fixture
def make_client(data_dir: Path):
    """Build a test client for a fresh app, connecting from ``peer`` (this computer by default)."""

    def make(peer: str = "127.0.0.1", **kwargs) -> TestClient:
        kwargs.setdefault("base_url", BASE_URL)
        # Like the dashboard page: browsers send Origin on every POST/PATCH/DELETE.
        kwargs.setdefault("headers", {"Origin": kwargs["base_url"]})
        return TestClient(create_app(), client=(peer, 50000), **kwargs)

    return make


@pytest.fixture
def client(make_client) -> TestClient:
    """Test client that looks like it's connecting from this computer."""
    return make_client()


@pytest.fixture
def make_account(client: TestClient):
    """Create a fake account through the API and return its JSON."""

    def make(**overrides) -> dict:
        body = {"name": "Test Checking", "kind": "checking", **overrides}
        response = client.post("/api/local/accounts", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return make


@pytest.fixture
def add_txn(client: TestClient):
    """Create a fake transaction through the API and return its JSON."""

    def add(account_id: int, amount_cents: int | None, **overrides) -> dict:
        body = {"account_id": account_id, "date": "2026-01-15", "description": "Fake"}
        body |= {"amount_cents": amount_cents, **overrides}
        response = client.post("/api/local/transactions", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return add
