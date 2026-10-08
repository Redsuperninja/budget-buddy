"""Stopping with the program that started the Home Base (BUDGET_BUDDY_STOP_WITH_PID), and the parts
the packaged Home Base needs (a bundled dashboard, no console)."""

import os
import subprocess
import sys
import threading

import pytest
import uvicorn

import app.__main__ as entry
from app.dashboard_files import default_dashboard_dir
from app.parent_watch import process_alive, stop_when_gone


def test_this_process_is_alive_and_a_finished_one_is_not():
    assert process_alive(os.getpid())
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert not process_alive(child.pid)


def test_stop_is_called_once_the_process_ends():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)"])
    stopped = threading.Event()
    stop_when_gone(child.pid, stopped.set, interval=0.05)
    assert not stopped.is_set()
    child.wait()
    assert stopped.wait(timeout=5)


def test_a_process_already_gone_stops_at_once():
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    stopped = threading.Event()
    stop_when_gone(child.pid, stopped.set, interval=0.05)
    assert stopped.wait(timeout=5)


def test_polling_is_used_off_windows(monkeypatch):
    import app.parent_watch as watch

    monkeypatch.setattr(watch.sys, "platform", "linux")
    alive = iter([True, False])
    monkeypatch.setattr(watch, "process_alive", lambda pid: next(alive))
    stopped = threading.Event()
    watch.stop_when_gone(1234, stopped.set, interval=0.01)
    assert stopped.wait(timeout=5)


def test_serve_watches_the_given_process(data_dir, monkeypatch):
    watched = []
    monkeypatch.setenv("BUDGET_BUDDY_STOP_WITH_PID", "4242")
    monkeypatch.setattr(entry, "stop_when_gone", lambda pid, stop: watched.append((pid, stop)))
    servers = []
    monkeypatch.setattr(uvicorn.Server, "run", lambda self: servers.append(self))
    entry.serve()
    (pid, stop), (server,) = watched[0], servers
    assert pid == 4242
    stop()
    assert server.should_exit is True


def test_serve_without_the_setting_watches_nothing(data_dir, monkeypatch):
    monkeypatch.delenv("BUDGET_BUDDY_STOP_WITH_PID", raising=False)
    monkeypatch.setattr(entry, "stop_when_gone", lambda *a: pytest.fail("should not watch"))
    monkeypatch.setattr(uvicorn.Server, "run", lambda self: None)
    entry.serve()


def test_stop_with_pid_must_be_a_process_id(data_dir, monkeypatch):
    from pydantic import ValidationError

    from app.config import Settings

    monkeypatch.setenv("BUDGET_BUDDY_STOP_WITH_PID", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_windowed_build_gets_somewhere_to_write(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    entry._give_output_somewhere()
    assert sys.stdout is not None and sys.stderr is not None
    sys.stdout.close()
    sys.stderr.close()


def test_packaged_home_base_uses_its_bundled_dashboard(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert default_dashboard_dir() == tmp_path / "dashboard"
    monkeypatch.delattr(sys, "frozen")
    assert default_dashboard_dir().name == "dashboard"
    assert default_dashboard_dir() != tmp_path / "dashboard"
