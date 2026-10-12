"""Encrypted sync (roadmap #15): who may call, token checks, and body checks.

Uses a fake phone that pairs through the real flow (tests/fake_phone.py). Fake data only.
"""

import pytest
from fake_phone import LAN_BASE, SNAPSHOT, error_code, seen_nonce_count
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.bodylimit import read_limited
from app.crypto.b64url import b64u_encode
from app.errors import ApiError
from app.models import Device

# --- who may call, and from where -----------------------------------------------------------


def test_lan_phone_reaches_sync_but_not_the_dashboard_routes(phone):
    assert phone.call(SNAPSHOT)[0].status_code == 200
    response = phone.http.get("/api/local/accounts")
    assert response.status_code == 403 and error_code(response) == "not_this_computer"


def test_public_addresses_get_not_home_network(dashboard, phone):
    outside = TestClient(dashboard.app, client=("203.0.113.7", 50000), base_url=LAN_BASE)
    response = outside.post(SNAPSHOT, content=b"{}")
    assert response.status_code == 403 and error_code(response) == "not_home_network"


def test_unknown_host_header_is_bad_host(phone):
    response, _ = phone.call(SNAPSHOT, headers={"Host": "evil.example:8765"})
    assert response.status_code == 403 and error_code(response) == "bad_host"


# --- token checks come first --------------------------------------------------------------


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer", "Bearer "])
def test_missing_token_is_not_paired(phone, header):
    headers = {} if header is None else {"Authorization": header}
    response, _ = phone.call(SNAPSHOT, token=None, headers=headers)
    assert response.status_code == 401 and error_code(response) == "not_paired"


def test_unknown_token_is_not_paired(phone):
    response, _ = phone.call(SNAPSHOT, token=b64u_encode(bytes(32)))
    assert response.status_code == 401 and error_code(response) == "not_paired"


@pytest.mark.parametrize(
    "token", ["short", "AAAAA", "x" * 43 + "=", "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3"]
)
def test_malformed_token_is_bad_request(phone, token):
    response, _ = phone.call(SNAPSHOT, token=token)
    assert response.status_code == 400 and error_code(response) == "bad_request"


def test_token_is_checked_before_the_body_is_read(phone):
    reads = []

    def body():
        for _ in range(100):
            reads.append(1)
            yield b"x" * 1024

    response = phone.http.post(
        SNAPSHOT, content=body(), headers={"Authorization": f"Bearer {b64u_encode(bytes(32))}"}
    )
    assert response.status_code == 401
    assert len(reads) < 100  # the server did not drain the upload


def test_revoked_device_is_refused_and_its_nonces_deleted(phone, dashboard):
    phone.ok(SNAPSHOT)
    assert seen_nonce_count(phone) == 1
    assert dashboard.post(f"/api/local/devices/{phone.device_id}/revoke").status_code == 200
    assert seen_nonce_count(phone) == 0
    response, _ = phone.call(SNAPSHOT)
    assert response.status_code == 401 and error_code(response) == "device_revoked"
    with Session(dashboard.app.state.engine) as session:
        device = session.get(Device, phone.device_id)
        assert device.revoked and device.sync_key is None


# --- body checks --------------------------------------------------------------------------


def test_wrong_content_type_is_bad_request(phone):
    response, _ = phone.call(SNAPSHOT, headers={"Content-Type": "text/plain"})
    assert response.status_code == 400 and error_code(response) == "bad_request"


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"v":1}', b""])
def test_garbage_body_is_bad_request(phone, body):
    response, _ = phone.call(SNAPSHOT, body=body)
    assert response.status_code == 400 and error_code(response) == "bad_request"


def test_bad_envelope_fields_are_bad_request(phone):
    good, _ = phone.envelope(SNAPSHOT)
    for change in (
        {"nonce": b64u_encode(bytes(23))},
        {"nonce": "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3="},
        {"box": "AAAA"},  # 3 bytes: shorter than the 16-byte tag
        {"box": good["box"] + "\n"},
        {"ts": "1790000000"},
        {"ts": True},
    ):
        response, _ = phone.call(SNAPSHOT, body=good | change)
        assert response.status_code == 400, change
        assert error_code(response) == "bad_request", change


def test_unsupported_envelope_version_is_update_needed(phone):
    good, _ = phone.envelope(SNAPSHOT)
    response, _ = phone.call(SNAPSHOT, body=good | {"v": 2})
    assert response.status_code == 426 and error_code(response) == "update_needed"
    assert response.json()["error"]["supported"] == [1]


def test_oversize_body_is_413_by_content_length(phone):
    response, _ = phone.call(SNAPSHOT, body=b"x" * (16 * 1024 + 1))
    assert response.status_code == 413 and error_code(response) == "too_large"


def test_oversize_body_is_413_while_streaming(phone):
    def body():  # no Content-Length: the server has to count as it reads
        for _ in range(100):
            yield b"x" * 4096

    response = phone.http.post(
        SNAPSHOT,
        content=body(),
        headers={"Authorization": f"Bearer {phone.token}", "Content-Type": "application/json"},
    )
    assert response.status_code == 413 and error_code(response) == "too_large"


def test_reader_stops_pulling_chunks_at_the_limit():
    import asyncio

    pulled = []

    class FakeRequest:
        headers = {}  # no Content-Length

        async def stream(self):
            for _ in range(1000):
                pulled.append(1)
                yield b"x" * 1024

    with pytest.raises(ApiError) as caught:
        asyncio.run(read_limited(FakeRequest(), 16 * 1024))
    assert caught.value.status == 413 and len(pulled) == 17


def test_body_at_the_limit_is_still_read(phone):
    response, _ = phone.call(SNAPSHOT, body=b" " * (16 * 1024))
    assert response.status_code == 400  # read in full, then rejected as not an envelope
