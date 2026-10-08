"""Where the programs are: this app (for its window, or starting with Windows) and the Home Base."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOME_BASE_EXE = Path("home-base") / "Budget Buddy Home Base.exe"


def is_frozen() -> bool:
    """True inside ``Budget Buddy.exe`` (built with PyInstaller), False when run from Python."""
    return bool(getattr(sys, "frozen", False))


def _windowless(python: Path) -> str:
    """pythonw runs without a console window; fall back to python if it isn't there."""
    pythonw = python.with_name("pythonw.exe")
    return str(pythonw if pythonw.exists() else python)


def launch_command(*args: str) -> list[str]:
    if is_frozen():
        return [sys.executable, *args]
    return [_windowless(Path(sys.executable)), "-m", "budget_buddy_desktop", *args]


def command_line(*args: str) -> str:
    """The same command as one line of text, quoted for Windows (for the Run registry key)."""
    return subprocess.list2cmdline(launch_command(*args))


def spawn(*args: str) -> subprocess.Popen:
    return subprocess.Popen(launch_command(*args), close_fds=True)


def home_base_command() -> list[str]:
    """The packaged Home Base beside ``Budget Buddy.exe``, or the server from this repo's source."""
    if is_frozen():
        return [str(Path(sys.executable).parent / HOME_BASE_EXE)]
    python = REPO / "server" / ".venv" / "Scripts" / "python.exe"
    return [_windowless(python), "-m", "app"]
