"""The light parts (roadmap 22b): tray, start with Windows, one tray at a time, relaunching, and the
port check. The registry and the tray library are faked, so this runs anywhere."""

import subprocess
import sys

import pytest

from budget_buddy_desktop import autostart, commands, probe, single_instance
from budget_buddy_desktop.tray import Tray


class FakeRegistry:
    """Just enough of ``winreg`` for the Run key."""

    HKEY_CURRENT_USER = "HKCU"
    REG_SZ = 1

    def __init__(self):
        self.values = {}

    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def OpenKey(self, root, path):  # noqa: N802 (winreg's names)
        return self._Key()

    CreateKey = OpenKey

    def QueryValueEx(self, key, name):  # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, value):  # noqa: N802
        self.values[name] = value

    def DeleteValue(self, key, name):  # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


def test_start_with_windows_on_and_off():
    reg = FakeRegistry()
    assert not autostart.is_enabled(reg)
    autostart.set_enabled(True, reg)
    assert autostart.is_enabled(reg)
    assert reg.values["Budget Buddy"].endswith("--background")
    autostart.set_enabled(False, reg)
    assert not autostart.is_enabled(reg)
    autostart.set_enabled(False, reg)  # turning it off twice is fine


def test_commands_from_python(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert commands.launch_command("--window")[-3:] == ["-m", "budget_buddy_desktop", "--window"]
    home_base = commands.home_base_command()
    assert home_base[-2:] == ["-m", "app"]
    assert "server" in home_base[0]


def test_commands_inside_the_exe(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\Budget Buddy\Budget Buddy.exe")
    assert commands.launch_command("--background") == [sys.executable, "--background"]
    assert commands.command_line("--background") == (
        '"C:\\Apps\\Budget Buddy\\Budget Buddy.exe" --background'
    )
    (home_base,) = commands.home_base_command()
    assert home_base.endswith("home-base\\Budget Buddy Home Base.exe") or home_base.endswith(
        "home-base/Budget Buddy Home Base.exe"
    )


def test_spawn_starts_the_command(monkeypatch):
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: started.append(cmd) or "process")
    assert commands.spawn("--window") == "process"
    assert started[0][-1] == "--window"


@pytest.mark.parametrize(
    ("value", "expected"), [("", 8765), ("8799", 8799), ("0", 8765), ("x", 8765)]
)
def test_port_follows_the_server_setting(monkeypatch, value, expected):
    monkeypatch.setenv("BUDGET_BUDDY_PORT", value)
    assert probe.port() == expected


def test_is_running_is_false_when_nothing_answers():
    assert probe.is_running(1, timeout=0.2) is False


@pytest.mark.skipif(sys.platform != "win32", reason="named mutexes are Windows-only")
def test_only_one_tray_at_a_time():
    name = "Local\\BudgetBuddyTest-" + str(id(object()))
    with single_instance.first_instance(name) as first:
        assert first
        with single_instance.first_instance(name) as second:
            assert not second
    with single_instance.first_instance(name) as again:
        assert again  # released when the first one ended


def test_elsewhere_there_is_never_a_block(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with single_instance.first_instance() as first:
        assert first


class FakeProcess:
    def __init__(self, running):
        self.running = running

    def poll(self):
        return None if self.running else 0


class FakeIcon:
    def __init__(self):
        self.notes = []

    def notify(self, text):
        self.notes.append(text)


def test_tray_opens_one_window_at_a_time(monkeypatch):
    spawned = []
    monkeypatch.setattr(commands, "spawn", lambda *a: spawned.append(a) or FakeProcess(True))
    tray, icon = Tray(8765), FakeIcon()
    tray.open_window(icon)
    tray.open_window(icon)  # still open: a note instead of a second window
    assert spawned == [("--window",)]
    assert "already open" in icon.notes[0]
    tray.window = FakeProcess(False)  # closed: open again
    tray.open_window()
    assert len(spawned) == 2


def test_tray_status_and_autostart_toggle(monkeypatch):
    monkeypatch.setattr(probe, "is_running", lambda port, timeout: True)
    assert "phones can sync" in Tray(8765).status()
    monkeypatch.setattr(probe, "is_running", lambda port, timeout: False)
    assert "Resting" in Tray(8765).status()
    reg = FakeRegistry()
    monkeypatch.setattr(autostart, "_winreg", lambda: reg)
    Tray.toggle_autostart()
    assert autostart.is_enabled()
    Tray.toggle_autostart()
    assert not autostart.is_enabled()


def test_the_tray_loads_no_window_library():
    """Light start: importing the launcher and tray doesn't load the window (WebView2) library."""
    code = (
        "import sys, budget_buddy_desktop.launcher, budget_buddy_desktop.tray; "
        "print('webview' in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_icon(tmp_path):
    pytest.importorskip("PIL")
    from budget_buddy_desktop.icon import make_icon, save_ico

    assert make_icon(64).size == (64, 64)
    path = tmp_path / "icon.ico"
    save_ico(path)
    assert path.read_bytes()[:4] == b"\x00\x00\x01\x00"  # the .ico header
