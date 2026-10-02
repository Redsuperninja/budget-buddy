"""Settings for the Home Base, read from environment variables (prefix ``BUDGET_BUDDY_``)."""

import os
import sys
from pathlib import Path

from pydantic import Field
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
    ``BUDGET_BUDDY_DEV_MODE``.
    """

    model_config = SettingsConfigDict(env_prefix="BUDGET_BUDDY_")

    data_dir: Path = Field(default_factory=default_data_dir)
    # This computer only until phone pairing ships. Set to 0.0.0.0 to allow the home network.
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    # Developer extras such as the /docs API explorer. Off for normal use.
    dev_mode: bool = False
