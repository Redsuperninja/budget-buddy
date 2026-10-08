"""Is a Home Base answering on this computer? A light check the tray can afford to make often."""

import os
import urllib.request

DEFAULT_PORT = 8765


def port() -> int:
    """The Home Base's port: ``BUDGET_BUDDY_PORT`` if set (as the server reads it), else 8765."""
    text = os.environ.get("BUDGET_BUDDY_PORT", "")
    return int(text) if text.isdigit() and 0 < int(text) < 65536 else DEFAULT_PORT


def local_url(on_port: int) -> str:
    return f"http://127.0.0.1:{on_port}"


def is_running(on_port: int, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"{local_url(on_port)}/api/health", timeout=timeout) as reply:
            return reply.status == 200
    except OSError:
        return False
