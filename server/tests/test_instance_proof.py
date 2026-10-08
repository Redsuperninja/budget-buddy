"""The desktop app's check that the Home Base on the port is really Budget Buddy, and new dashboard
files being found without a restart."""

import asyncio
import hashlib
import hmac
import json

import pytest

from app import instance_proof

NONCE = "ab" * 16


def test_proof(client):
    key = client.app.state.instance_key
    reply = client.get("/api/local/instance/proof", params={"nonce": NONCE})
    expected = hmac.new(bytes.fromhex(key), NONCE.encode(), hashlib.sha256).hexdigest()
    assert reply.json() == {"proof": expected}
    assert reply.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("bound", [True, False])
def test_running_file_only_once_the_port_is_ours(data_dir, monkeypatch, bound):
    """A second copy that can't bind the port must not replace or remove the first one's file."""
    import uvicorn

    from app.config import Settings
    from app.serving import build_server

    data_dir.mkdir(parents=True)
    instance_proof.write(data_dir, 8765, "aa" * 32)  # the copy already running

    async def fake_startup(self, sockets=None):
        self.started = bound

    async def fake_shutdown(self, sockets=None):
        pass

    monkeypatch.setattr(uvicorn.Server, "startup", fake_startup)
    monkeypatch.setattr(uvicorn.Server, "shutdown", fake_shutdown)
    server = build_server(Settings())
    asyncio.run(server.startup())
    saved = json.loads((data_dir / instance_proof.FILE_NAME).read_text(encoding="ascii"))
    assert saved["key"] == (server.config.app.state.instance_key if bound else "aa" * 32)
    if bound:
        assert saved["port"] == 8765
    asyncio.run(server.shutdown())
    assert (data_dir / instance_proof.FILE_NAME).exists() is (not bound)


def test_a_bad_nonce_is_refused(client):
    for nonce in ("short", "zz" * 16, "ab" * 70):
        assert client.get("/api/local/instance/proof", params={"nonce": nonce}).status_code == 422


def test_the_proof_is_this_computer_only(make_client):
    lan = make_client("192.168.1.50", base_url="http://192.168.1.20:8765")
    reply = lan.get("/api/local/instance/proof", params={"nonce": NONCE})
    assert reply.status_code == 403


def test_shutdown_leaves_someone_elses_file(data_dir):
    data_dir.mkdir(parents=True)
    instance_proof.write(data_dir, 8765, "11" * 32)
    instance_proof.remove(data_dir, "22" * 32)
    assert (data_dir / instance_proof.FILE_NAME).exists()


def test_a_dashboard_file_added_while_running_is_served(client, fake_dashboard, monkeypatch):
    from app import dashboard_files

    monkeypatch.setattr(dashboard_files, "RESCAN_SECONDS", 0.0)
    assert client.get("/static/js/screens/new.js").status_code == 404
    (fake_dashboard / "js" / "screens" / "new.js").write_text(
        "export const n = 1;", encoding="utf-8"
    )
    assert client.get("/static/js/screens/new.js").text == "export const n = 1;"
    # Still only files that pass the same rules.
    (fake_dashboard / "js" / "notes.txt").write_text("x", encoding="utf-8")
    assert client.get("/static/js/notes.txt").status_code == 404


def test_rescans_are_limited(client, fake_dashboard):
    client.get("/static/js/missing.js")  # rescans once
    (fake_dashboard / "js" / "late.js").write_text("export const n = 1;", encoding="utf-8")
    assert client.get("/static/js/late.js").status_code == 404  # too soon for another rescan
