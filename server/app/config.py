"""Settings for the Home Base, read from environment variables (prefix ``BUDGET_BUDDY_``)."""

import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_data_dir() -> Path:
    """Where user data lives by default. Always outside the repo."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "BudgetBuddy"
    return Path.home() / ".local" / "share" / "budget-buddy"


class Settings(BaseSettings):
    """Runtime settings.

    Override with env vars: ``BUDGET_BUDDY_DATA_DIR``, ``BUDGET_BUDDY_HOST``, ``BUDGET_BUDDY_PORT``,
    ``BUDGET_BUDDY_DEV_MODE``, ``BUDGET_BUDDY_KEY_STORE``, ``BUDGET_BUDDY_INSECURE_TEST_KEYSTORE``.
    """

    model_config = SettingsConfigDict(env_prefix="BUDGET_BUDDY_")

    data_dir: Path = Field(default_factory=default_data_dir)
    # This computer only until phone pairing ships. Set to 0.0.0.0 to allow the home network.
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    # The computer's home-network address that goes into the pairing QR. Leave empty to detect it.
    lan_ip: str | None = None
    # Friendly name the phone shows for this computer (at most 50 characters).
    server_name: str = Field(default="Home Base", min_length=1, max_length=50)
    # Developer extras such as the /docs API explorer. Off for normal use.
    dev_mode: bool = False
    # Where the encryption key is kept: the OS password vault ("keyring"), or "memory" for
    # automated tests and CI only (the key is lost when the process ends).
    key_store: Literal["keyring", "memory"] = "keyring"
    # Second, separate switch that must also be on before "memory" is allowed, so the memory key
    # store can't be turned on by accident in normal use (security review H1, PR #22).
    insecure_test_keystore: bool = False

    @field_validator("lan_ip", mode="before")
    @classmethod
    def _lan_ip_is_private(cls, value):
        if value in (None, ""):
            return None
        from app.network import is_loopback_address, is_private_address

        if not is_private_address(value) or is_loopback_address(value):
            raise ValueError(
                "BUDGET_BUDDY_LAN_IP must be a home-network address such as 192.168.1.20."
            )
        return value

    @model_validator(mode="after")
    def _memory_key_store_needs_test_switch(self) -> "Settings":
        if self.key_store == "memory" and not self.insecure_test_keystore:
            from app.crypto.errors import KeyStoreError

            raise KeyStoreError(
                "BUDGET_BUDDY_KEY_STORE=memory is only for automated tests. It loses the "
                "encryption key when Budget Buddy stops, which would make your data unreadable. "
                "Remove that setting to keep the key in this computer's password vault."
            )
        return self
