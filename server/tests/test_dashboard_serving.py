"""Serving the dashboard (roadmap #16, ADR-0005): this computer only, locked down, offline.

Runs against the fake dashboard folder from ``conftest.py``, never the real ``dashboard/``.
"""

import logging
import os
import subprocess
import sys

import pytest

from app.dashboard_files import MAX_FILE_BYTES, default_dashboard_dir, load_dashboard


def _code(response) -> str:
    return response.json()["error"]["code"]


def _write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def test_index_loads_the_main_module(client):
    assert 'src="/static/js/main.js"' in client.get("/").text
    assert client.get("/static/js/main.js").status_code == 200


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
    assert "unsafe-inline" not in response.headers["content-security-policy"]


def test_pages_are_isolated_from_other_windows(client):
    assert client.get("/").headers["cross-origin-opener-policy"] == "same-origin"
    assert client.get("/static/js/main.js").headers["cross-origin-opener-policy"] == "same-origin"


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
        "package.json",
        "tests/x.test.js",
        ".hidden.js",
        "js/.hidden.js",
    ],
)
def test_only_the_listed_dashboard_files_are_served(make_client, fake_dashboard, name):
    _write(fake_dashboard / "package.json", "{}")
    _write(fake_dashboard / "tests" / "x.test.js")
    _write(fake_dashboard / ".hidden.js")
    _write(fake_dashboard / "js" / ".hidden.js")
    assert make_client().get(f"/static/{name}").status_code == 404


def test_the_allowlist_is_every_script_and_style_file_and_nothing_else(make_client, fake_dashboard):
    _write(fake_dashboard / "js" / "api" / "endpoints.js")
    _write(fake_dashboard / "package.json", "{}")
    _write(fake_dashboard / "notes.txt")
    _write(fake_dashboard / "js" / "readme.md")
    assets = make_client().app.state.dashboard.assets
    assert set(assets) == {"app.css", "js/main.js", "js/screens/home.js", "js/api/endpoints.js"}


def test_symlinks_are_never_served(make_client, fake_dashboard, tmp_path):
    secret = tmp_path / "secret.js"
    secret.write_text("secret", encoding="utf-8")
    try:
        (fake_dashboard / "js" / "linked.js").symlink_to(secret)
        (fake_dashboard / "linked.css").symlink_to(secret)
        (fake_dashboard / "js" / "dir-link").symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not allow symbolic links")
    client = make_client()
    assert set(client.app.state.dashboard.assets) == {"app.css", "js/main.js", "js/screens/home.js"}
    for name in ("js/linked.js", "linked.css", "js/dir-link/secret.js"):
        assert client.get(f"/static/{name}").status_code == 404


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are a Windows feature")
def test_junctions_inside_the_folder_are_never_served(make_client, fake_dashboard):
    junction = fake_dashboard / "js" / "again"
    made = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(fake_dashboard / "js" / "screens")],
        capture_output=True,
    )
    if made.returncode != 0:
        pytest.skip("could not create a junction here")
    try:
        client = make_client()
        assert set(client.app.state.dashboard.assets) == {
            "app.css",
            "js/main.js",
            "js/screens/home.js",
        }
        assert client.get("/static/js/again/home.js").status_code == 404
    finally:
        os.rmdir(junction)  # removes the junction only, never the folder it points to


def test_hard_linked_files_are_not_served(make_client, fake_dashboard, tmp_path):
    outside = tmp_path / "outside.js"
    outside.write_text("secret", encoding="utf-8")
    try:
        os.link(outside, fake_dashboard / "js" / "hard.js")
    except OSError:
        pytest.skip("this system does not allow hard links")
    client = make_client()
    assert "js/hard.js" not in client.app.state.dashboard.assets
    assert client.get("/static/js/hard.js").status_code == 404


def test_a_file_swapped_for_a_link_after_startup_is_not_served(
    make_client, fake_dashboard, tmp_path
):
    client = make_client()
    secret = tmp_path / "secret.js"
    secret.write_text("secret", encoding="utf-8")
    target = fake_dashboard / "js" / "main.js"
    target.unlink()
    try:
        target.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not allow symbolic links")
    assert client.get("/static/js/main.js").status_code == 404


def test_oversized_files_are_not_served(make_client, fake_dashboard):
    _write(fake_dashboard / "js" / "big.js", "x" * (MAX_FILE_BYTES + 1))
    client = make_client()
    assert "js/big.js" not in client.app.state.dashboard.assets
    assert client.get("/static/js/big.js").status_code == 404


def test_dashboard_dir_setting_is_honoured(make_client, tmp_path, monkeypatch):
    other = tmp_path / "other"
    _write(other / "index.html", "<p>other __CSRF_TOKEN__</p>")
    monkeypatch.setenv("BUDGET_BUDDY_DASHBOARD_DIR", str(other))
    assert "<p>other " in make_client().get("/").text


def test_the_default_folder_is_dashboard_at_the_repo_root():
    folder = default_dashboard_dir()
    assert folder.name == "dashboard"
    assert (folder.parent / "server" / "app").is_dir()


# --- API-only mode: no dashboard folder ---


@pytest.fixture
def api_only_client(make_client, tmp_path, monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_DASHBOARD_DIR", str(tmp_path / "does-not-exist"))
    return make_client()


def test_without_the_folder_the_api_still_works(api_only_client):
    assert api_only_client.app.state.dashboard is None
    assert api_only_client.get("/api/health").status_code == 200
    assert api_only_client.get("/api/local/accounts").json() == []
    assert api_only_client.get("/api/local/csrf-token").status_code == 200
    created = api_only_client.post("/api/local/accounts", json={"name": "X", "kind": "checking"})
    assert created.status_code == 201


def test_without_the_folder_the_page_says_so_in_plain_english(api_only_client):
    response = api_only_client.get("/")
    assert response.status_code == 404
    assert "dashboard files weren't found" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert api_only_client.get("/static/js/main.js").status_code == 404


def test_a_folder_without_index_html_means_api_only(tmp_path, caplog):
    folder = tmp_path / "empty"
    _write(folder / "js" / "main.js")
    with caplog.at_level(logging.WARNING, logger="app.dashboard"):
        assert load_dashboard(folder) is None
    assert "Running without the web page" in caplog.text


def test_a_file_in_place_of_the_folder_means_api_only(tmp_path):
    not_a_folder = tmp_path / "dashboard"
    _write(not_a_folder)
    assert load_dashboard(not_a_folder) is None


# --- this computer only ---

# Another computer that hasn't joined (ADR-0009) gets the page and its files, but no token and no
# data; the scripts' token stays on this computer.
PAGE_PATHS = ["/", "/static/js/main.js", "/static/app.css"]


@pytest.mark.parametrize("path", PAGE_PATHS)
def test_other_computers_get_only_the_page(make_client, path):
    lan = make_client("192.168.1.50", base_url="http://192.168.1.20:8765")
    response = lan.get(path)
    assert response.status_code == 200
    assert lan.app.state.csrf_token not in response.text


@pytest.mark.parametrize("path", ["/api/local/csrf-token", "/api/local/accounts"])
def test_dashboard_api_is_this_computer_only(make_client, path):
    lan = make_client("192.168.1.50", base_url="http://192.168.1.20:8765")
    response = lan.get(path)
    assert response.status_code == 403
    assert _code(response) == "not_this_computer"


def test_dashboard_refuses_a_foreign_host(make_client):
    response = make_client().get("/", headers={"Host": "attacker.example:8765"})
    assert response.status_code == 403
    assert _code(response) == "bad_host"


# --- pairing QR (the Connect phone page shows it) ---


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
