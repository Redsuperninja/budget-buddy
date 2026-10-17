from pathlib import Path

import pytest
from fake_phone import NOW, Phone, lan_client, pair_phone
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(autouse=True)
def memory_key_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep encryption keys in memory: tests must never touch the real OS password vault."""
    monkeypatch.setenv("BUDGET_BUDDY_KEY_STORE", "memory")
    monkeypatch.setenv("BUDGET_BUDDY_INSECURE_TEST_KEYSTORE", "1")


@pytest.fixture(autouse=True, scope="session")
def no_real_password_vault():
    """If a test still reaches for the keyring (say after monkeypatch.undo()), it fails loudly
    instead of writing a key into this computer's real vault. test_keys.py sets its own fakes."""
    import keyring
    import keyring.backends.fail

    previous = keyring.get_keyring()
    keyring.set_keyring(keyring.backends.fail.Keyring())
    yield
    keyring.set_keyring(previous)


@pytest.fixture(autouse=True)
def fixed_lan_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never depend on the real network: pretend this computer is 192.168.1.20."""
    monkeypatch.setenv("BUDGET_BUDDY_LAN_IP", "192.168.1.20")


FAKE_INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="csrf-token" content="__CSRF_TOKEN__"><title>Budget Buddy</title>
<link rel="stylesheet" href="/static/app.css">
<script type="module" src="/static/js/main.js"></script></head>
<body><h1>Budget Buddy</h1></body></html>
"""


@pytest.fixture(autouse=True)
def fake_dashboard(tmp_path_factory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tiny stand-in for ``dashboard/``, so server tests never read the real dashboard files."""
    folder = tmp_path_factory.mktemp("fake-dashboard")  # not inside the test's own tmp_path
    (folder / "js" / "screens").mkdir(parents=True)
    (folder / "index.html").write_text(FAKE_INDEX, encoding="utf-8")
    (folder / "app.css").write_text("body { margin: 0; }", encoding="utf-8")
    (folder / "js" / "main.js").write_text("export const started = true;", encoding="utf-8")
    (folder / "js" / "screens" / "home.js").write_text("export const home = 1;", encoding="utf-8")
    monkeypatch.setenv("BUDGET_BUDDY_DASHBOARD_DIR", str(folder))
    return folder


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
        app = create_app()
        # ...and the CSRF token the page carries (tests that set their own X-CSRF-Token win).
        headers = dict(kwargs.pop("headers"))
        if not any(k.lower() == "x-csrf-token" for k in headers):
            headers["X-CSRF-Token"] = app.state.csrf_token
        return TestClient(app, client=(peer, 50000), headers=headers, **kwargs)

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


@pytest.fixture
def app_client(make_client):
    """The local dashboard client plus a phone-side client (home network) for the same app."""
    dashboard = make_client()
    dashboard.app.state.clock = lambda: NOW
    return dashboard, lan_client(dashboard.app)


@pytest.fixture
def start(app_client):
    """Start pairing from the dashboard; returns the response JSON (with the QR payload)."""
    dashboard, _ = app_client

    def go() -> dict:
        response = dashboard.post("/api/local/pairing")
        assert response.status_code == 200, response.text
        return response.json()

    return go


@pytest.fixture
def dashboard(make_client) -> TestClient:
    """The local dashboard client, for tests that also use a fake phone."""
    return make_client()


@pytest.fixture
def phone(dashboard) -> Phone:
    """A fake phone paired with ``dashboard`` through the real flow, ready to sync."""
    return pair_phone(dashboard)


@pytest.fixture
def checking(make_account) -> int:
    """The ID of a fake checking account."""
    return make_account()["id"]
