"""Pairing (roadmap #14): start a QR and the Home Base identity. Fake data only."""

import hashlib
import json
import sqlite3

from fake_phone import (
    NOW,
    error_code,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_decode
from app.db import database_path
from app.models import PairingSession


def test_start_returns_the_qr_payload(app_client, start):
    started = start()
    payload = started["payload"]
    assert set(payload) == {
        "v",
        "app",
        "host",
        "port",
        "code",
        "pair_pub",
        "server_id",
        "name",
        "exp",
    }
    assert payload["v"] == 1 and payload["app"] == "budget-buddy"
    assert payload["host"] == "192.168.1.20" and payload["port"] == 8765
    assert payload["name"] == "Home Base"
    assert payload["exp"] == NOW + 600 and started["seconds_valid"] == 600
    b64u_decode(payload["code"], 16)
    b64u_decode(payload["pair_pub"], 32)
    b64u_decode(payload["server_id"], 16)
    # "Show code as text": the same payload, ready to paste into the phone.
    assert json.loads(started["payload_text"]) == payload
    assert "\n" not in started["payload_text"]


def test_start_response_is_not_cached(app_client):
    dashboard, _ = app_client
    response = dashboard.post("/api/local/pairing")
    assert response.headers["cache-control"] == "no-store"


def test_server_id_is_stable_between_runs(make_client):
    first = make_client().app.state.server_id
    assert make_client().app.state.server_id == first


def test_code_is_stored_only_as_a_hash(app_client, start, data_dir):
    payload = start()["payload"]
    raw = (
        sqlite3.connect(database_path(data_dir))
        .execute("SELECT code_hash, pair_pub, pair_sk FROM pairing_sessions")
        .fetchone()
    )
    assert raw[0] == hashlib.sha256(payload["code"].encode()).hexdigest()
    assert raw[1] == payload["pair_pub"]
    assert isinstance(raw[2], bytes) and raw[2][0] == 1  # encrypted at rest
    database = database_path(data_dir).read_bytes()
    assert payload["code"].encode() not in database


def test_start_is_this_computer_only(make_client):
    lan = make_client("192.168.1.30")
    response = lan.post("/api/local/pairing")
    assert response.status_code == 403 and error_code(response) == "not_this_computer"


def test_start_needs_a_page_on_this_computer(make_client):
    response = make_client(headers={}).post("/api/local/pairing")
    assert response.status_code == 403 and error_code(response) == "bad_origin"


def test_start_without_a_home_network(make_client, monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_LAN_IP", "")
    monkeypatch.setattr("app.lan.detect_lan_ip", lambda: None)
    monkeypatch.setattr("app.main.detect_lan_ip", lambda: None)
    response = make_client().post("/api/local/pairing")
    assert response.status_code == 409 and error_code(response) == "no_home_network"


def test_old_session_keys_are_erased_at_startup_and_when_listing_devices(
    app_client, start, make_client
):
    dashboard, _ = app_client
    start()
    dashboard.app.state.clock = lambda: NOW + 601

    def key_left():
        with Session(dashboard.app.state.engine) as session:
            return session.scalars(select(PairingSession.pair_sk)).one()

    assert key_left() is not None
    dashboard.get("/api/local/devices")
    assert key_left() is None

    start_app = make_client()
    start_app.app.state.clock = lambda: NOW
    start_app.post("/api/local/pairing")
    start_app.app.state.clock = lambda: NOW + 601
    with start_app:  # runs the app's startup
        pass
    with Session(start_app.app.state.engine) as session:
        assert all(k is None for k in session.scalars(select(PairingSession.pair_sk)))


def test_health_reports_contract(client):
    assert client.get("/api/health").json()["contract"] == 1
