"""The computer dashboard (roadmap #16): served on this computer only, locked down, offline."""

import re
from pathlib import Path

import pytest

import app.dashboard as dashboard_package

BASE_URL = "http://127.0.0.1:8765"
ACCOUNTS = "/api/local/accounts"
DASHBOARD_DIR = Path(dashboard_package.__file__).parent
DASHBOARD_FILES = sorted(
    p for p in DASHBOARD_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts
)
JS_FILES = sorted(DASHBOARD_DIR.rglob("*.js"))


def _code(response) -> str:
    return response.json()["error"]["code"]


def test_index_is_served_with_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "img-src 'self' data: blob:" in csp
    assert "unsafe-inline" not in csp
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert "Budget Buddy" in response.text


def test_index_carries_this_runs_csrf_token(client):
    token = client.app.state.csrf_token
    assert f'<meta name="csrf-token" content="{token}">' in client.get("/").text
    assert "__CSRF_TOKEN__" not in client.get("/").text


@pytest.mark.parametrize(
    ("name", "content_type"),
    [
        ("js/main.js", "text/javascript"),
        ("js/screens/home.js", "text/javascript"),
        ("app.css", "text/css"),
    ],
)
def test_static_assets_have_the_right_type(client, name, content_type):
    response = client.get(f"/static/{name}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    "name",
    [
        "__init__.py",
        "index.html",
        "../main.py",
        "nothing.js",
        "js",
        "js/",
        "js/screens/",
        "js/../index.html",
        "js/%2e%2e/index.html",
        "%2e%2e/main.py",
        "js/main.js.map",
        "js/main.JS",
        "..%2f..%2fmain.py",
        "%5cjs%5cmain.js",
    ],
)
def test_only_the_dashboard_assets_are_served(client, name):
    assert client.get(f"/static/{name}").status_code == 404


LOCAL_PATHS = ["/", "/static/js/main.js", "/static/app.css", "/api/local/csrf-token"]


@pytest.mark.parametrize("path", LOCAL_PATHS)
def test_dashboard_is_this_computer_only(make_client, path):
    lan = make_client("192.168.1.50", base_url="http://192.168.1.20:8765")
    response = lan.get(path)
    assert response.status_code == 403
    assert _code(response) == "not_this_computer"


def test_dashboard_refuses_a_foreign_host(make_client):
    response = make_client().get("/", headers={"Host": "attacker.example:8765"})
    assert response.status_code == 403
    assert _code(response) == "bad_host"


def test_pairing_qr_is_an_svg_picture(client):
    response = client.post("/api/local/pairing")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["qr_svg"].startswith("<svg")
    assert "<script" not in body["qr_svg"]
    assert response.headers["cache-control"] == "no-store"


def test_pairing_qr_needs_this_computer(make_client):
    lan = make_client("192.168.1.50", base_url="http://192.168.1.20:8765")
    response = lan.post("/api/local/pairing", headers={"Origin": "http://192.168.1.20:8765"})
    assert response.status_code == 403


def test_dashboard_files_make_no_internet_requests():
    assert DASHBOARD_FILES
    for path in DASHBOARD_FILES:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"https?://|//cdn|@import|url\(", text), path.name
        assert "innerHTML" not in text and "eval(" not in text, path.name
    html = (Path(dashboard_package.__file__).parent / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)  # no inline script
    assert " style=" not in html and "<style" not in html


def test_screens_fill_through_the_helper_that_skips_empty_parts():
    # el.replaceChildren(null) shows the word "null" on the page; fill() skips empty parts.
    assert JS_FILES
    for path in JS_FILES:
        assert "replaceChildren(" not in path.read_text(encoding="utf-8"), path.name


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


def test_refusals_have_the_headers_too(make_client):
    response = make_client().get("/api/health", headers={"Host": "attacker.example:8765"})
    assert response.status_code == 403
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"


def test_dashboard_pages_are_isolated_from_other_windows(client):
    assert client.get("/").headers["cross-origin-opener-policy"] == "same-origin"
    assert client.get("/static/js/main.js").headers["cross-origin-opener-policy"] == "same-origin"


def test_phone_routes_from_home_network_need_no_origin_or_csrf_token(make_client):
    phone = make_client("192.168.1.50", base_url="http://192.168.1.20:8765", headers={})
    for path in ("/api/pair", "/api/sync/x"):
        response = phone.post(path, json={})
        assert response.status_code != 403 or _code(response) != "bad_origin", path


def test_every_script_and_style_file_is_served_and_nothing_else():
    from app.routers.dashboard import ASSETS

    on_disk = {
        p.relative_to(DASHBOARD_DIR).as_posix()
        for p in DASHBOARD_FILES
        if p.suffix in {".js", ".css"}
    }
    assert set(ASSETS) == on_disk
    assert "js/main.js" in ASSETS and "app.css" in ASSETS


def test_index_loads_the_main_module(client):
    assert 'src="/static/js/main.js"' in client.get("/").text
    assert client.get("/static/js/main.js").status_code == 200
