"""Checking that the Home Base already on the port is really Budget Buddy (genuine.py). A tiny
stand-in server answers the challenge with the key from a fake data folder, or with a wrong one."""

import hashlib
import hmac
import http.server
import json
import threading
import urllib.parse

import pytest

from budget_buddy_desktop import genuine

KEY = "11" * 32


def serve(key: str):
    class Proof(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            nonce = query["nonce"][0]
            body = {
                "proof": hmac.new(bytes.fromhex(key), nonce.encode(), hashlib.sha256).hexdigest()
            }
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Proof)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(tmp_path))
    return tmp_path


def write(folder, port, key=KEY):
    (folder / genuine.FILE_NAME).write_text(json.dumps({"port": port, "pid": 1, "key": key}))


def test_the_real_home_base_proves_itself(folder):
    server = serve(KEY)
    try:
        write(folder, server.server_port)
        assert genuine.is_budget_buddy(server.server_port)
    finally:
        server.shutdown()


def test_a_look_alike_cant(folder):
    server = serve("22" * 32)  # doesn't know the key in the data folder
    try:
        write(folder, server.server_port)
        assert not genuine.is_budget_buddy(server.server_port)
    finally:
        server.shutdown()


@pytest.mark.parametrize(
    "contents", [None, "not json", '{"port": 1}', '{"port": "x", "key": "zz"}']
)
def test_no_or_bad_running_file(folder, contents):
    if contents is not None:
        (folder / genuine.FILE_NAME).write_text(contents)
    assert not genuine.is_budget_buddy(1)


def test_the_file_is_for_another_port(folder):
    write(folder, 1234)
    assert not genuine.is_budget_buddy(4321)


def test_nothing_answers(folder):
    write(folder, 9)  # the discard port: nothing listens
    assert not genuine.is_budget_buddy(9, timeout=0.5)


def test_default_data_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("BUDGET_BUDDY_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    if genuine.sys.platform == "win32":
        assert genuine.data_dir() == tmp_path / "BudgetBuddy"
    monkeypatch.delenv("LOCALAPPDATA")
    assert genuine.data_dir().name in ("BudgetBuddy", "budget-buddy")
