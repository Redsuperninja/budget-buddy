"""Proving to the desktop app that the Home Base on this port really is Budget Buddy (ADR-0008).

The desktop app won't show whatever answers on the port, since it could be a look-alike collecting
data. So while it runs, the Home Base keeps a random key in a file in the private data folder
(``home-base-running.json``: port, process ID, key) and answers a challenge with it: the app sends a
fresh random nonce to ``GET /api/local/instance/proof`` and checks the HMAC-SHA256 of it. Only a
program that can read this user's data folder can know the key. The file is removed on shutdown,
and replaced on the next start. The key is never logged or sent.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path

from app.crypto._fs import write_private_bytes

FILE_NAME = "home-base-running.json"
NONCE = re.compile(r"^[0-9a-f]{32,128}$")


def new_key() -> str:
    return secrets.token_hex(32)


def write(data_dir: Path, port: int, key: str) -> None:
    body = {"port": port, "pid": os.getpid(), "key": key}
    write_private_bytes(data_dir / FILE_NAME, json.dumps(body).encode("ascii"))


def remove(data_dir: Path, key: str) -> None:
    """Remove the file, but only if it's still ours (another start may have replaced it)."""
    path = data_dir / FILE_NAME
    try:
        if json.loads(path.read_text(encoding="ascii")).get("key") == key:
            path.unlink()
    except (OSError, ValueError):
        pass


def proof(key: str, nonce: str) -> str:
    return hmac.new(bytes.fromhex(key), nonce.encode("ascii"), hashlib.sha256).hexdigest()
