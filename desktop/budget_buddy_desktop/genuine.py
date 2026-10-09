"""Is the Home Base already answering on the port really Budget Buddy? Then the window can use it
instead of refusing to start (ADR-0008).

The Home Base keeps a random key in ``home-base-running.json`` in the private data folder while it
runs (server ``app/instance_proof.py``). This sends a fresh random challenge to it and checks the
HMAC-SHA256 answer against that key. A look-alike program on the port can't answer, because it
can't read this user's data folder. Only a "yes" lets the window show the page.
"""

import ctypes
import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path

from budget_buddy_desktop.probe import local_url, open_local

FILE_NAME = "home-base-running.json"
_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259


def data_dir() -> Path:
    """Budget Buddy's data folder, worked out the way the Home Base does (``BUDGET_BUDDY_DATA_DIR``,
    else the default). A copy of the server's rule: parts never import each other's code."""
    chosen = os.environ.get("BUDGET_BUDDY_DATA_DIR")
    if chosen:
        return Path(chosen)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "BudgetBuddy"
    return Path.home() / ".local" / "share" / "budget-buddy"


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == _STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def is_budget_buddy(port: int, timeout: float = 2.0) -> bool:
    try:
        saved = json.loads((data_dir() / FILE_NAME).read_text(encoding="ascii"))
        key = bytes.fromhex(saved["key"])
        if saved["port"] != port or not process_alive(int(saved["pid"])):
            return False  # for another port, or left behind by a crash
    except (OSError, ValueError, KeyError, TypeError):
        return False
    nonce = secrets.token_hex(16)
    try:
        url = f"{local_url(port)}/api/local/instance/proof?nonce={nonce}"
        with open_local(url, timeout=timeout) as reply:
            answer = json.loads(reply.read(4096))["proof"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    expected = hmac.new(key, nonce.encode("ascii"), hashlib.sha256).hexdigest()
    return isinstance(answer, str) and hmac.compare_digest(answer, expected)
