"""While a Home Base runs it holds an OS lock on ``<data folder>/home-base.lock``.

A restore (ADR-0012) takes the same lock before it swaps any files, so it can never move data out
from under a running Home Base, also on macOS and Linux, where open files can be renamed. The OS
releases the lock if the process ends any way at all, so a crash can't leave it stuck.
"""

import sys
from pathlib import Path
from typing import BinaryIO

from app.db import make_private_file

FILE_NAME = "home-base.lock"


def try_lock(data_dir: Path) -> BinaryIO | None:
    """The locked file (keep it open to hold the lock), or None if something else holds it."""
    path = data_dir / FILE_NAME
    make_private_file(path)
    handle = open(path, "r+b")  # noqa: SIM115 (held open for as long as the lock is)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def release(handle: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    handle.close()  # closing also releases flock
