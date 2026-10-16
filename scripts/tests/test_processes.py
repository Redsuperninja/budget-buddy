"""Waiting for a Home Base and stopping what a script started, on any platform."""

import socket
import subprocess
import sys

import _processes


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_nothing_answers_on_a_free_port():
    port = free_port()
    assert not _processes.port_in_use(port)
    assert not _processes.health_ok(port)


def test_a_listening_port_is_in_use():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        assert _processes.port_in_use(s.getsockname()[1])


def test_stop_tree_stops_a_background_process_and_what_it_started():
    # A child that starts a grandchild, as the .venv's python.exe does on Windows.
    sleep = "import time; time.sleep(60)"
    grandchild = (
        f"import subprocess, sys; subprocess.Popen([sys.executable, '-c', {sleep!r}]); {sleep}"
    )
    flags = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    process = subprocess.Popen([sys.executable, "-c", grandchild], **flags)
    _processes.stop_tree(process)
    assert process.poll() is not None


def test_stop_tree_leaves_a_process_that_stops_by_itself():
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    _processes.stop_tree(process, grace=10)
    assert process.returncode == 0
