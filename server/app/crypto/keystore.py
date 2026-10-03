"""Where the master key lives: the OS password vault (normal use) or memory (tests and CI)."""

import base64
import binascii
import hashlib
import os
import threading
from pathlib import Path
from typing import Literal, Protocol

from app.crypto.errors import KeyStoreError

SERVICE_NAME = "budget-buddy"

KeyStoreKind = Literal["keyring", "memory"]


def key_name_for(data_dir: Path) -> str:
    """The vault entry name for one data folder.

    Derived from the folder's full path, so a test folder and your real folder never share
    (or overwrite) a key. The path itself isn't stored in the vault, only a hash of it.
    """
    resolved = os.path.normcase(str(Path(data_dir).resolve()))
    return "data-" + hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:32]


class KeyStore(Protocol):
    def get(self, name: str) -> bytes | None:
        """The stored key, or ``None`` if there isn't one."""

    def set(self, name: str, key: bytes) -> None:
        """Store (or replace) a key."""


class MemoryKeyStore:
    """Keeps keys in this process only. For tests and CI: keys vanish when the process ends."""

    def __init__(self) -> None:
        self._keys: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def get(self, name: str) -> bytes | None:
        with self._lock:
            return self._keys.get(name)

    def set(self, name: str, key: bytes) -> None:
        with self._lock:
            self._keys[name] = bytes(key)


_NO_VAULT_MESSAGE = (
    "Budget Buddy couldn't use this computer's password vault to keep its encryption key safe. "
    "On Windows this is Credential Manager, on macOS the Keychain, and on Linux a Secret Service "
    "such as GNOME Keyring or KWallet. Make sure one is installed and unlocked, then try again."
)


class KeyringKeyStore:
    """Keeps keys in the OS password vault via the ``keyring`` package."""

    def __init__(self, service: str = SERVICE_NAME) -> None:
        self.service = service

    @staticmethod
    def _keyring():
        import keyring
        import keyring.backends.fail

        if isinstance(keyring.get_keyring(), keyring.backends.fail.Keyring):
            raise KeyStoreError(_NO_VAULT_MESSAGE)
        return keyring

    def get(self, name: str) -> bytes | None:
        import keyring.errors

        kr = self._keyring()
        try:
            stored = kr.get_password(self.service, name)
        except keyring.errors.KeyringError as exc:
            raise KeyStoreError(_NO_VAULT_MESSAGE) from exc
        if stored is None:
            return None
        try:
            return base64.b64decode(stored, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise KeyStoreError(
                "Budget Buddy's encryption key in the password vault looks damaged."
            ) from exc

    def set(self, name: str, key: bytes) -> None:
        import keyring.errors

        kr = self._keyring()
        try:
            kr.set_password(self.service, name, base64.b64encode(key).decode("ascii"))
        except keyring.errors.KeyringError as exc:
            raise KeyStoreError(_NO_VAULT_MESSAGE) from exc


# One shared memory store per process, so starting the app twice in a test reuses the same key.
_MEMORY_STORE = MemoryKeyStore()


def get_key_store(kind: KeyStoreKind) -> KeyStore:
    if kind == "memory":
        return _MEMORY_STORE
    if kind == "keyring":
        return KeyringKeyStore()
    raise ValueError(f"Unknown key store: {kind!r}")
