"""Shared by the scripts: where things are, plain messages, and installing a part into its .venv.

Standard library only, and the same on Windows, macOS and Linux. Importing it checks the Python
version first, so every script says "needs Python 3.12" in plain English instead of failing oddly.
A script in this folder imports it directly; one in a subfolder puts this folder on ``sys.path``
first (scripts/README.md).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

WINDOWS = sys.platform == "win32"
REPO = Path(__file__).resolve().parent.parent
SERVER_DIR = REPO / "server"
MOBILE_DIR = REPO / "mobile"
DESKTOP_DIR = REPO / "desktop"
LAUNCH_DIR = REPO / "launch"
PACKAGING_DIR = REPO / "packaging" / "windows"

_COLORS = {"green": "32", "yellow": "33", "cyan": "36"}


def _colors_on() -> bool:
    """True if this window shows colors (on Windows, after switching them on)."""
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if not WINDOWS:
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle, mode = kernel32.GetStdHandle(-11), ctypes.c_uint32()  # -11: this window's output
    return bool(
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        and kernel32.SetConsoleMode(handle, mode.value | 4)
    )


_USE_COLOR = _colors_on()


def say(message: str = "", color: str | None = None) -> None:
    """Print a line, in color (green, yellow or cyan) when the window can show it."""
    if color and _USE_COLOR:
        message = f"\033[{_COLORS[color]}m{message}\033[0m"
    print(message, flush=True)


def stop(message: str, code: int = 1) -> NoReturn:
    """Say what went wrong, in plain English, and end the script."""
    say(message, "yellow")
    raise SystemExit(code)


def set_title(title: str) -> None:
    """Name this window, so it's easy to find among others."""
    if WINDOWS:
        import ctypes

        ctypes.windll.kernel32.SetConsoleTitleW(title)
    elif sys.stdout.isatty():
        print(f"\033]0;{title}\007", end="", flush=True)


# Whatever Python started the script, which may be older than the scripts' target version.
if sys.version_info < (3, 12):  # noqa: UP036
    stop(
        "Budget Buddy needs Python 3.12 or newer. "
        "Install it from https://www.python.org/downloads/ "
        "(on Windows, tick 'Add python.exe to PATH'), then try again."
    )


def command_for(script: str) -> str:
    """How to run a script from the Budget Buddy folder, for messages: ``py scripts/x.py`` on
    Windows (Python takes / there too) and ``python3 scripts/x.py`` elsewhere."""
    return ("py " if WINDOWS else "python3 ") + script


def venv_python(part_dir: Path) -> Path:
    """The Python inside a part's own .venv."""
    return part_dir / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")


def open_file(path: Path) -> None:
    """Open a file in its usual app (a picture viewer for a .png). Raises OSError if it can't."""
    if WINDOWS:
        os.startfile(path)  # noqa: S606 -- a file this script just made
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        try:
            subprocess.Popen([opener, str(path)], stderr=subprocess.DEVNULL)
        except FileNotFoundError as exc:
            raise OSError(f"{opener} isn't available") from exc


def rerun_with(python: Path) -> None:
    """Run this script again with ``python`` (a part's .venv, which has its packages) and end with
    its exit code, unless this already is that Python."""
    if Path(sys.prefix).resolve() == python.parent.parent.resolve():
        return
    command = [str(python), sys.argv[0], *sys.argv[1:]]
    if not WINDOWS:
        os.execv(command[0], command)  # becomes that Python, so Ctrl+C and exit codes just work
    try:
        raise SystemExit(subprocess.run(command).returncode)
    except KeyboardInterrupt:  # the other Python got the Ctrl+C too
        raise SystemExit(130) from None


def run(command: list, cwd: Path, failure: str) -> None:
    """Run a command; if it fails, end the script with the plain-English ``failure``."""
    if subprocess.run([str(part) for part in command], cwd=cwd).returncode != 0:
        stop(failure)


def install_part(part_dir: Path, extras: tuple[str, ...], label: str) -> Path:
    """Install a part (server or desktop) into its own .venv, or update it when its pyproject.toml
    or the extras (e.g. "dev", "build") changed since last time; a stamp in .venv remembers.
    Returns the .venv's Python."""
    python = venv_python(part_dir)
    stamp = part_dir / ".venv" / "budget-buddy-install.txt"
    digest = hashlib.sha256((part_dir / "pyproject.toml").read_bytes()).hexdigest().upper()
    if python.exists() and stamp.exists():
        had_digest, _, had = stamp.read_text(encoding="ascii").strip().partition(" ")
        if had_digest == digest and set(extras) <= set(filter(None, had.split(","))):
            return python
    say(f"Installing {label} (this can take a few minutes the first time)...")
    if not python.exists():
        hint = (
            ""
            if WINDOWS
            else " On Ubuntu or Debian, install python3-venv first (sudo apt install python3-venv)."
        )
        run([sys.executable, "-m", "venv", ".venv"], part_dir, f"Setting up {label} failed.{hint}")
    run(
        [python, "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
        part_dir,
        f"Installing {label} failed.",
    )
    target = f".[{','.join(extras)}]" if extras else "."
    run(
        [python, "-m", "pip", "install", "--quiet", "-e", target],
        part_dir,
        f"Installing {label} failed.",
    )
    stamp.write_text(f"{digest} {','.join(extras)}", encoding="ascii")
    return python


def install_home_base(dev: bool = False) -> Path:
    """The Home Base. ``dev`` adds the developer tools (tests, linter) that testers' setup uses."""
    return install_part(SERVER_DIR, ("dev",) if dev else (), "the Home Base")
