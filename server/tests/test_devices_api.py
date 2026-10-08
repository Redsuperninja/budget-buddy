"""Pairing (roadmap #14): list and remove phones."""

import os

import pytest
from fake_phone import (
    error_code,
    pair_named,
)
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_encode
from app.models import Device
from app.services import devices as device_service


def test_revoked_token_stops_working_at_once(app_client, start):
    dashboard, phone = app_client
    data = pair_named(phone, start)
    response = dashboard.post(f"/api/local/devices/{data['device_id']}/revoke")
    assert response.status_code == 200
    assert response.json()["revoked"] is True and response.json()["revoked_at"]

    with Session(dashboard.app.state.engine) as session:
        with pytest.raises(Exception) as caught:
            device_service.authenticate_token(session, data["token"])
        assert (caught.value.status, caught.value.code) == (401, "device_revoked")
        device = session.get(Device, data["device_id"])
        assert device.sync_key is None  # the key is deleted, the row stays
    # Listed with history, and removing twice is harmless.
    assert dashboard.get("/api/local/devices").json()[0]["revoked"] is True
    assert dashboard.post(f"/api/local/devices/{data['device_id']}/revoke").status_code == 200


def test_unknown_and_malformed_tokens(app_client):
    dashboard, _ = app_client
    with Session(dashboard.app.state.engine) as session:
        for token, status, code in [
            (b64u_encode(os.urandom(32)), 401, "not_paired"),
            ("not a token", 400, "bad_request"),
            (None, 400, "bad_request"),
        ]:
            with pytest.raises(Exception) as caught:
                device_service.authenticate_token(session, token)
            assert (caught.value.status, caught.value.code) == (status, code)


def test_revoking_one_phone_leaves_the_other(app_client, start):
    dashboard, phone = app_client
    first = pair_named(phone, start, "First")
    second = pair_named(phone, start, "Second")
    dashboard.post(f"/api/local/devices/{first['device_id']}/revoke")
    listed = {d["name"]: d["revoked"] for d in dashboard.get("/api/local/devices").json()}
    assert listed == {"First": True, "Second": False}
    with Session(dashboard.app.state.engine) as session:
        assert device_service.authenticate_token(session, second["token"]).name == "Second"


def test_revoke_unknown_device_is_a_plain_404(app_client):
    dashboard, _ = app_client
    response = dashboard.post("/api/local/devices/99/revoke")
    assert response.status_code == 404 and error_code(response) == "not_found"


def test_device_routes_are_this_computer_only(make_client):
    lan = make_client("192.168.1.30")
    assert lan.get("/api/local/devices").status_code == 403
    assert lan.post("/api/local/devices/1/revoke").status_code == 403


def test_paired_phone_is_noticed_without_refreshing_settings(app_client, start):
    dashboard, phone = app_client
    assert dashboard.get("/api/local/devices").json() == []
    pair_named(phone, start, "Ana's iPhone")
    assert [d["name"] for d in dashboard.get("/api/local/devices").json()] == ["Ana's iPhone"]
