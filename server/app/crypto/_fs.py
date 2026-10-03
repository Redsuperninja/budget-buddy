"""Small file helpers: private (owner-only on macOS/Linux) and atomic writes."""

import os
import sys
import uuid
from pathlib import Path


def ensure_private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(path, 0o700)


def write_private_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically, readable only by this user on macOS/Linux.

    Writes to a temporary file in the same folder first, so a crash never leaves half a file.
    """
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if sys.platform != "win32":
            os.chmod(tmp, 0o600)  # os.open's mode is reduced by the umask
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
