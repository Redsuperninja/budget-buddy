"""The window process (roadmap 22): starting the Home Base as its own program, plain-English
start-up problems, reusing a running Home Base, the window, and choosing the mode. A tiny stand-in
Home Base (Python's built-in web server) stands in for the real one; the window is faked."""

import socket
import sys
import textwrap
import types
from contextlib import contextmanager

import pytest

from budget_buddy_desktop import genuine, launcher, probe
from budget_buddy_desktop import home_base as home_base_module
from budget_buddy_desktop.home_base import GENERAL_PROBLEM, HomeBase, StartFailed, explain

STAND_IN = textwrap.dedent(
    """
    import http.server, os, sys
    print("stand-in starting", flush=True)
    assert os.environ["BUDGET_BUDDY_STOP_WITH_PID"].isdigit()
    class Health(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
        def log_message(self, *a):
            pass
    http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), Health).serve_forever()
    """
)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def port(monkeypatch):
    chosen = free_port()
    monkeypatch.setenv("BUDGET_BUDDY_PORT", str(chosen))
    return chosen


def use_home_base(monkeypatch, *args):
    monkeypatch.setattr(home_base_module, "home_base_command", lambda: [sys.executable, *args])


def test_home_base_starts_as_its_own_program(monkeypatch, port):
    use_home_base(monkeypatch, "-c", STAND_IN, str(port))
    home_base = HomeBase(port)
    home_base.start()
    try:
        assert probe.is_running(port)
        assert home_base.url == f"http://127.0.0.1:{port}"
    finally:
        home_base.process.kill()
        home_base.process.wait()
    assert "stand-in starting" in home_base.output


def test_its_own_plain_english_error_is_shown(monkeypatch, port):
    use_home_base(
        monkeypatch,
        "-c",
        'print("Budget Buddy can\'t open your data folder."); raise SystemExit(1)',
    )
    with pytest.raises(StartFailed, match="can't open your data folder"):
        HomeBase(port).start()


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["ERROR: [Errno 10048] error while attempting to bind on address"], "couldn't use port"),
        (["[Errno 98] Address already in use"], "couldn't use port"),
        (["Traceback (most recent call last):", "ValueError: raw"], GENERAL_PROBLEM),
        (["ValueError: raw internals"], GENERAL_PROBLEM),
        ([], GENERAL_PROBLEM),
        (["", "Your recovery phrase is needed.", ""], "Your recovery phrase is needed."),
    ],
)
def test_explain(lines, expected):
    assert expected in explain(lines, 8765)


def test_too_slow_to_start(monkeypatch, port):
    use_home_base(monkeypatch, "-c", "import time; time.sleep(30)")
    monkeypatch.setattr(home_base_module, "START_TIMEOUT_SECONDS", 0.5)
    with pytest.raises(StartFailed, match="too long"):
        HomeBase(port).start()


@pytest.fixture
def fake_webview(monkeypatch):
    calls = []
    module = types.SimpleNamespace(
        settings={},
        create_window=lambda *a, **kw: calls.append(("window", a, kw)),
        start=lambda **kw: calls.append(("start", kw)),
    )
    monkeypatch.setitem(sys.modules, "webview", module)
    return module, calls


def test_window_shows_the_dashboard_and_allows_downloads(fake_webview, tmp_path):
    from budget_buddy_desktop.window import show_dashboard

    module, calls = fake_webview
    show_dashboard("http://127.0.0.1:8765", tmp_path)
    assert module.settings["ALLOW_DOWNLOADS"] is True
    assert calls[0][1] == ("Budget Buddy", "http://127.0.0.1:8765")
    assert calls[1] == ("start", {"private_mode": False, "storage_path": str(tmp_path)})


def test_problem_window_escapes_the_message(fake_webview):
    from budget_buddy_desktop.window import show_problem

    _, calls = fake_webview
    show_problem("<b>port</b> busy")
    assert "&lt;b&gt;port&lt;/b&gt; busy" in calls[0][2]["html"]


@pytest.fixture
def shown(monkeypatch):
    seen = []
    import budget_buddy_desktop.window as window

    monkeypatch.setattr(window, "show_dashboard", lambda url, storage: seen.append(("dash", url)))
    monkeypatch.setattr(window, "show_problem", lambda message: seen.append(("problem", message)))
    return seen


def test_window_starts_its_own_home_base(monkeypatch, port, shown):
    started = []
    monkeypatch.setattr(HomeBase, "start", lambda self: started.append(self.port))
    assert launcher.run_window() == 0
    assert started == [port]
    assert shown == [("dash", f"http://127.0.0.1:{port}")]


def test_never_shows_something_else_on_the_port(monkeypatch, port):
    use_home_base(monkeypatch, "-c", "raise SystemExit('should not start')")
    monkeypatch.setattr(probe, "is_running", lambda p, timeout=1.0: True)
    monkeypatch.setattr(genuine, "is_budget_buddy", lambda p: False)
    with pytest.raises(StartFailed, match="Something else is using port"):
        HomeBase(port).start()


def test_a_running_budget_buddy_is_reused(monkeypatch, port):
    use_home_base(monkeypatch, "-c", "raise SystemExit('should not start')")
    monkeypatch.setattr(probe, "is_running", lambda p, timeout=1.0: True)
    monkeypatch.setattr(genuine, "is_budget_buddy", lambda p: True)
    home_base = HomeBase(port)
    home_base.start()
    assert home_base.reused and home_base.process is None


def test_start_up_problem_gets_a_window(monkeypatch, port, shown):
    def fail(self):
        raise StartFailed("Port busy.")

    monkeypatch.setattr(HomeBase, "start", fail)
    assert launcher.run_window() == 1
    assert shown == [("problem", "Port busy.")]


def test_window_storage_is_beside_the_data_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert launcher.window_storage() == tmp_path / "BudgetBuddy-Window"


@pytest.fixture
def modes(monkeypatch):
    seen = []
    monkeypatch.setattr(launcher, "run_window", lambda: seen.append("window") or 0)
    monkeypatch.setattr(launcher.commands, "spawn", lambda *a: seen.append(("spawn", a)))

    class FakeTray:
        def __init__(self, port):
            seen.append(("tray", port))

        def run(self, open_now):
            seen.append(("open_now", open_now))

    import budget_buddy_desktop.tray as tray

    monkeypatch.setattr(tray, "Tray", FakeTray)
    return seen


def _instance(monkeypatch, first: bool):
    @contextmanager
    def fake(name=None):
        yield first

    monkeypatch.setattr(launcher, "first_instance", fake)


def test_modes(modes, monkeypatch):
    monkeypatch.delenv("BUDGET_BUDDY_PORT", raising=False)
    assert launcher.main(["--window"]) == 0
    _instance(monkeypatch, first=True)
    launcher.main([])
    launcher.main(["--background"])
    _instance(monkeypatch, first=False)
    launcher.main([])  # tray already showing: just a window
    launcher.main(["--background"])  # at login with a tray already showing: nothing
    assert modes == [
        "window",
        ("tray", 8765),
        ("open_now", True),
        ("tray", 8765),
        ("open_now", False),
        ("spawn", ("--window",)),
    ]


def test_windowed_program_gets_somewhere_to_write(monkeypatch):
    from budget_buddy_desktop.__main__ import give_output_somewhere

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    give_output_somewhere()
    assert sys.stdout is not None and sys.stderr is not None
    sys.stdout.close()
    sys.stderr.close()
