"""The desktop app's check that the Home Base on the port is really Budget Buddy, and new dashboard
files being found without a restart."""

import hashlib
import hmac
import json

from app import instance_proof

NONCE = "ab" * 16


def test_running_file_and_proof(make_client, data_dir):
    client = make_client()
    with client:  # runs start-up and shutdown
        saved = json.loads((data_dir / instance_proof.FILE_NAME).read_text(encoding="ascii"))
        assert saved["port"] == 8765 and saved["key"] == client.app.state.instance_key
        reply = client.get("/api/local/instance/proof", params={"nonce": NONCE})
        expected = hmac.new(bytes.fromhex(saved["key"]), NONCE.encode(), hashlib.sha256).hexdigest()
        assert reply.json() == {"proof": expected}
        assert reply.headers["cache-control"] == "no-store"
    assert not (data_dir / instance_proof.FILE_NAME).exists()


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
