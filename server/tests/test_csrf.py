"""Writes from the dashboard page: Origin and CSRF token rules, and headers on every response.

These test ``LocalAccessMiddleware``, not the page.
"""

import pytest

BASE_URL = "http://127.0.0.1:8765"
ACCOUNTS = "/api/local/accounts"


def _code(response) -> str:
    return response.json()["error"]["code"]


# --- writes: Origin and CSRF token ---


def test_dashboard_write_with_foreign_origin_is_refused(make_client):
    foreign = make_client(headers={"Origin": "http://attacker.example"})
    response = foreign.post(ACCOUNTS, json={"name": "X", "kind": "checking"})
    assert response.status_code == 403
    assert _code(response) == "bad_origin"
    assert foreign.get(ACCOUNTS).json() == []


def test_dashboard_write_without_origin_is_refused(make_client):
    c = make_client(headers={})
    assert c.post(ACCOUNTS, json={"name": "X", "kind": "checking"}).status_code == 403


def test_write_without_csrf_token_is_refused(make_client):
    c = make_client(headers={"Origin": BASE_URL, "X-CSRF-Token": ""})
    response = c.post(ACCOUNTS, json={"name": "X", "kind": "checking"})
    assert response.status_code == 403
    assert _code(response) == "bad_origin"
    assert c.get(ACCOUNTS).json() == []


def test_write_with_wrong_csrf_token_is_refused(make_client):
    c = make_client(headers={"Origin": BASE_URL, "X-CSRF-Token": "not-the-token"})
    writes = [("post", ACCOUNTS), ("patch", f"{ACCOUNTS}/1"), ("delete", f"{ACCOUNTS}/1")]
    for method, path in writes:
        response = c.request(method, path, json={"name": "X", "kind": "checking"})
        assert response.status_code == 403, method
        assert _code(response) == "bad_origin"


def test_write_with_the_right_csrf_token_works(client):
    token = client.get("/api/local/csrf-token").json()["token"]
    assert token == client.app.state.csrf_token
    response = client.post(
        ACCOUNTS, json={"name": "X", "kind": "checking"}, headers={"X-CSRF-Token": token}
    )
    assert response.status_code == 201


def test_csrf_token_is_new_every_run_and_not_sent_with_cors_headers(make_client):
    first, second = make_client(), make_client()
    assert first.app.state.csrf_token != second.app.state.csrf_token
    response = first.get("/api/local/csrf-token", headers={"Origin": "http://attacker.example"})
    assert "access-control-allow-origin" not in response.headers


# --- headers on every response; the phone's routes are not subject to the dashboard's CSRF rule ---


@pytest.mark.parametrize("path", ["/api/health", ACCOUNTS, "/", "/nothing-here"])
def test_every_response_has_nosniff_and_same_origin_resource_policy(client, path):
    response = client.get(path)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"


@pytest.mark.parametrize(
    "path",
    [ACCOUNTS, "/api/local/transactions", "/api/local/summary/monthly?month=2026-01", "/api/x"],
)
def test_api_replies_are_never_stored(client, path):
    """Financial data must not be kept in a browser's (or the desktop window's) disk cache."""
    assert client.get(path).headers["cache-control"] == "no-store"


def test_dashboard_files_keep_their_own_cache_rule(client):
    assert client.get("/").headers["cache-control"] == "no-store"
    assert client.get("/static/app.css").headers["cache-control"] == "no-cache"


def test_refusals_have_the_headers_too(make_client):
    response = make_client().get("/api/health", headers={"Host": "attacker.example:8765"})
    assert response.status_code == 403
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"


def test_phone_routes_from_home_network_need_no_origin_or_csrf_token(make_client):
    phone = make_client("192.168.1.50", base_url="http://192.168.1.20:8765", headers={})
    for path in ("/api/pair", "/api/sync/x"):
        response = phone.post(path, json={})
        assert response.status_code != 403 or _code(response) != "bad_origin", path
