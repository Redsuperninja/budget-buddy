"""Checking that the Home Base already on the port is really Budget Buddy (genuine.py). A tiny
stand-in server answers the challenge with the key from a fake data folder, or with a wrong one."""

import hashlib
import hmac
import http.server
import json
import os
import re
import threading
import urllib.parse
from pathlib import Path

import pytest

from budget_buddy_desktop import genuine, probe

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


def write(folder, port, key=KEY, pid=None):
    body = {"port": port, "pid": pid or os.getpid(), "key": key}  # a live process: this one
    (folder / genuine.FILE_NAME).write_text(json.dumps(body))


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


def test_a_file_left_by_a_crash_is_ignored(folder):
    server = serve(KEY)
    try:
        write(folder, server.server_port, pid=2**30)  # no such process
        assert not genuine.is_budget_buddy(server.server_port)
    finally:
        server.shutdown()


def test_process_alive():
    assert genuine.process_alive(os.getpid())
    assert not genuine.process_alive(0)
    assert not genuine.process_alive(2**30)


# The handshake's published example (docs/api/desktop-handshake.md); the server's tests read it too.
DOC = Path(__file__).resolve().parents[2] / "docs" / "api" / "desktop-handshake.md"
EXAMPLE = json.loads(re.search(r"```json\n(.*?)```", DOC.read_text(encoding="utf-8"), re.S)[1])


def test_same_port_rule_as_the_home_base(monkeypatch):
    rule = EXAMPLE["port"]
    monkeypatch.delenv(rule["override_variable"], raising=False)
    assert probe.port() == rule["default"]
    monkeypatch.setenv(rule["override_variable"], "9123")
    assert probe.port() == 9123


def test_same_data_folder_rule_as_the_home_base(monkeypatch, tmp_path):
    rule = EXAMPLE["data_folder"]
    monkeypatch.setenv(rule["override_variable"], str(tmp_path / "chosen"))
    assert genuine.data_dir() == tmp_path / "chosen"
    monkeypatch.delenv(rule["override_variable"])
    monkeypatch.setattr(genuine.sys, "platform", "win32")
    variable, *rest = rule["windows"]
    monkeypatch.setenv(variable, str(tmp_path))
    assert genuine.data_dir() == tmp_path.joinpath(*rest)
    monkeypatch.setattr(genuine.sys, "platform", "linux")
    monkeypatch.setattr(genuine.Path, "home", lambda: tmp_path)
    assert genuine.data_dir() == tmp_path.joinpath(*rule["elsewhere"])


def test_same_running_file_and_proof_as_the_home_base(folder, monkeypatch):
    """A stand-in that answers exactly the example's proof, for the example's key and nonce."""
    assert genuine.FILE_NAME == EXAMPLE["running_file"]
    asked = []

    class Example(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            asked.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"proof": EXAMPLE["proof"]}).encode())

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Example)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(genuine.secrets, "token_hex", lambda _n: EXAMPLE["nonce"])
    try:
        write(folder, server.server_port, key=EXAMPLE["key"])
        assert genuine.is_budget_buddy(server.server_port)
        assert asked == [f"{EXAMPLE['proof_path']}?nonce={EXAMPLE['nonce']}"]
    finally:
        server.shutdown()
