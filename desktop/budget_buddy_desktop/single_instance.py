"""Only one tray icon at a time, using a named Windows mutex (released when the process ends)."""

import ctypes
import sys
from collections.abc import Iterator
from contextlib import contextmanager

ERROR_ALREADY_EXISTS = 183
TRAY_MUTEX = "Local\\BudgetBuddyTray"


@contextmanager
def first_instance(name: str = TRAY_MUTEX) -> Iterator[bool]:
    """True if this process is the first to hold ``name``; False if another one already does."""
    if sys.platform != "win32":  # the desktop app is Windows-only; elsewhere, never block
        yield True
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, name)
    already = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
    try:
        yield not already
    finally:
        if handle:
            kernel32.CloseHandle(handle)
