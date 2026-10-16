"""Running a Home Base from a script: waiting for it to answer, and stopping it (only it) after.

The same on Windows, macOS and Linux. Each Home Base a script starts is told the script's process
ID (``BUDGET_BUDDY_STOP_WITH_PID``), so it also stops by itself if the script's window is closed or
the script crashes.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from _common import SERVER_DIR, WINDOWS


def health_ok(port: int | str) -> bool:
    """True if a Home Base answers on this computer at ``port``."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as reply:
            return reply.status == 200
    except (OSError, ValueError):
        return False


def port_in_use(port: int) -> bool:
    """True if something on this computer already listens on ``port``."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def start_home_base(
    python: Path, env: dict[str, str], background: bool = False, **popen
) -> subprocess.Popen:
    """Start ``python -m app`` in server/. ``background`` puts it in its own process group, so
    Ctrl+C in this window doesn't reach it and :func:`stop_tree` can stop everything it started."""
    env = {**os.environ, **env, "BUDGET_BUDDY_STOP_WITH_PID": str(os.getpid())}
    if background:
        popen["creationflags" if WINDOWS else "start_new_session"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP if WINDOWS else True
        )
    return subprocess.Popen([str(python), "-m", "app"], cwd=SERVER_DIR, env=env, **popen)


def wait_until_up(port: int | str, process: subprocess.Popen, seconds: float = 30) -> bool:
    """Wait until the Home Base answers; False if it stopped or didn't answer in time."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and process.poll() is None:
        if health_ok(port):
            return True
        time.sleep(0.5)
    return False


def stop_tree(process: subprocess.Popen, grace: float = 0) -> None:
    """Stop ``process`` and what it started (on Windows the .venv's python.exe starts the real
    one), after giving it ``grace`` seconds to stop by itself."""
    try:
        process.wait(grace)
        return
    except (subprocess.TimeoutExpired, KeyboardInterrupt):  # a second Ctrl+C: don't wait any longer
        pass
    try:
        if WINDOWS:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
        elif os.getpgid(process.pid) == process.pid:  # its own group: stop the whole group
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:  # it stopped just now
        pass
    try:
        process.wait(10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@contextmanager
def stopped_afterwards(process: subprocess.Popen, grace: float = 10):
    """Make sure ``process`` has stopped when the block ends, also after Ctrl+C. A Home Base
    running in this window gets the Ctrl+C too and stops by itself, so it gets ``grace`` seconds
    first."""
    try:
        yield process
    except KeyboardInterrupt:
        pass
    finally:
        stop_tree(process, grace)
