"""Stop the Home Base when the program that started it stops (``BUDGET_BUDDY_STOP_WITH_PID``).

The desktop app (top-level ``desktop/``, ADR-0008) runs the Home Base as its own process and passes
its process ID. When that program ends, even by crashing, the Home Base shuts down cleanly instead
of running on with nobody to use it. On Windows the process is held by a handle opened at start-up,
so a later program that reuses the same ID can't keep the Home Base running.
"""

import ctypes
import os
import sys
import threading
import time
from collections.abc import Callable

_SYNCHRONIZE = 0x00100000
_WAIT_TIMEOUT = 0x102
_INFINITE = 0xFFFFFFFF


def _kernel32():
    return ctypes.WinDLL("kernel32", use_last_error=True)


def process_alive(pid: int) -> bool:
    if sys.platform == "win32":
        kernel32 = _kernel32()
        handle = kernel32.OpenProcess(_SYNCHRONIZE, False, pid)
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == _WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # signal 0 only checks that the process exists
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _waiter(pid: int, interval: float) -> Callable[[], None]:
    """A function that returns once process ``pid`` (as it is now) has ended."""
    if sys.platform == "win32":
        kernel32 = _kernel32()
        handle = kernel32.OpenProcess(_SYNCHRONIZE, False, pid)  # opened now, not later
        if not handle:
            return lambda: None  # already gone

        def wait_on_handle() -> None:
            kernel32.WaitForSingleObject(handle, _INFINITE)
            kernel32.CloseHandle(handle)

        return wait_on_handle

    def poll() -> None:
        while process_alive(pid):
            time.sleep(interval)

    return poll


def stop_when_gone(pid: int, stop: Callable[[], None], interval: float = 1.0) -> threading.Thread:
    """Call ``stop`` once process ``pid`` has ended."""
    wait = _waiter(pid, interval)

    def watch() -> None:
        wait()
        stop()

    thread = threading.Thread(target=watch, name="parent-watch", daemon=True)
    thread.start()
    return thread
