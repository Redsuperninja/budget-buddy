"""Pairing (roadmap #14): the home-network listener opens and closes with pairing."""

import time

import pytest
from fake_phone import (
    NOW,
    lan_client,
    open_reply,
    pair_once,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Device


class FakeServer:
    """Stands in for a uvicorn server: "runs" until told to stop."""

    instances: list = []

    def __init__(self, app, host, port, fail=False):
        self.host, self.port, self.fail = host, port, fail
        self.started = False
        self.should_exit = False
        FakeServer.instances.append(self)

    def run(self):
        if self.fail:
            return
        self.started = True
        while not self.should_exit:
            time.sleep(0.01)


@pytest.fixture
def lan_listener(make_client):
    """A client whose app can open its (fake) home-network listener."""
    FakeServer.instances = []

    def make(fail=False):
        client = make_client()
        client.app.state.clock = lambda: NOW
        listener = client.app.state.listener
        listener._make_server = lambda app, host, port: FakeServer(app, host, port, fail)
        listener.attach()
        return client, listener

    return make


def test_first_pairing_opens_the_listener_on_the_specific_lan_address(lan_listener):
    client, listener = lan_listener()
    assert not listener.reachable()  # nothing wanted yet: this computer only
    body = client.post("/api/local/pairing").json()
    assert body["phone_can_connect"] is True and body["message"] is None
    assert [(f.host, f.port) for f in FakeServer.instances] == [("192.168.1.20", 8765)]
    assert listener.bound_ip == "192.168.1.20"
    listener.close()


def test_listener_stays_while_a_phone_is_paired_and_closes_when_nothing_needs_it(lan_listener):
    client, listener = lan_listener()
    qr = client.post("/api/local/pairing").json()["payload"]
    phone = lan_client(client.app)
    response, shared, nonce = pair_once(phone, qr)
    device_id = open_reply(response, shared, nonce)["data"]["device_id"]
    client.get("/api/local/devices")
    assert listener.running  # a phone is paired
    client.post(f"/api/local/devices/{device_id}/revoke")
    assert not listener.running and listener.bound_ip is None  # no session, no active phone


def test_listener_closes_when_the_pairing_expires_unused(lan_listener):
    client, listener = lan_listener()
    client.post("/api/local/pairing")
    assert listener.running
    client.app.state.clock = lambda: NOW + 601
    client.get("/api/local/devices")
    assert not listener.running


def test_listener_is_wanted_on_start_when_a_phone_is_already_paired(
    app_client, start, lan_listener
):
    dashboard, phone = app_client
    pair_once(phone, start()["payload"])
    listener = dashboard.app.state.listener
    listener._make_server = lambda app, host, port: FakeServer(app, host, port)
    listener.attach()
    listener.sync_from_database()
    assert listener.running
    listener.close()


def test_phone_cant_connect_when_the_listener_fails(lan_listener):
    client, listener = lan_listener(fail=True)
    body = client.post("/api/local/pairing").json()
    assert body["phone_can_connect"] is False
    assert "home-network connection" in body["message"]


def test_phone_cant_connect_when_nobody_runs_the_listener(make_client):
    body = make_client().post("/api/local/pairing").json()  # never attached, like a test run
    assert body["phone_can_connect"] is False and body["message"]


def test_explicit_loopback_host_means_never_the_network(monkeypatch, lan_listener):
    monkeypatch.setenv("BUDGET_BUDDY_HOST", "127.0.0.1")
    client, listener = lan_listener()
    body = client.post("/api/local/pairing").json()
    assert body["phone_can_connect"] is False
    assert "only on this computer" in body["message"]
    assert FakeServer.instances == []


def test_explicit_network_host_is_reachable_without_a_second_listener(monkeypatch, lan_listener):
    monkeypatch.setenv("BUDGET_BUDDY_HOST", "0.0.0.0")
    client, _ = lan_listener()
    assert client.post("/api/local/pairing").json()["phone_can_connect"] is True
    assert FakeServer.instances == []


def test_default_host_is_not_treated_as_explicit(make_client):
    assert "host" not in make_client().app.state.settings.model_fields_set


def test_settings_reject_a_public_lan_ip(monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_LAN_IP", "8.8.8.8")
    with pytest.raises(ValueError):
        Settings()


def _free_port() -> int:
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_real_listener_stops_and_restarts_quickly_without_running_the_app_lifespan(
    make_client, monkeypatch
):
    port = _free_port()
    monkeypatch.setenv("BUDGET_BUDDY_PORT", str(port))
    client = make_client(base_url=f"http://127.0.0.1:{port}")
    listener = client.app.state.listener
    listener.attach()
    closed = []
    original_close = listener.close
    listener.close = lambda: (closed.append(1), original_close())  # app shutdown calls this
    started = time.monotonic()
    for _ in range(2):  # open, close, open again
        listener.sync(True, "127.0.0.1")
        assert listener.running
        listener.sync(False, "127.0.0.1")
        assert not listener.running
    assert time.monotonic() - started < 4  # no 5 second wait on a lock
    assert closed == []  # the second listener never ran the app's shutdown
    with Session(client.app.state.engine) as session:  # shared database is still open
        assert session.scalars(select(Device)).all() == []


@pytest.mark.parametrize("host", ["localhost", "LocalHost", "LOCALHOST.", "::1", "127.0.0.2"])
def test_explicit_loopback_names_count_as_never(monkeypatch, lan_listener, host):
    monkeypatch.setenv("BUDGET_BUDDY_HOST", host)
    _, listener = lan_listener()
    assert listener.never and not listener.main_is_on_network
