import os
import stat
import sys
from pathlib import Path

import pytest

from app.config import Settings, default_data_dir
from app.main import create_app


def test_defaults(monkeypatch):
    for var in (
        "BUDGET_BUDDY_DATA_DIR",
        "BUDGET_BUDDY_HOST",
        "BUDGET_BUDDY_PORT",
        "BUDGET_BUDDY_DEV_MODE",
        "BUDGET_BUDDY_KEY_STORE",
    ):
        monkeypatch.delenv(var, raising=False)
    settings = Settings()
    assert settings.data_dir == default_data_dir()
    assert settings.host == "127.0.0.1"
    assert settings.port == 8765
    assert settings.dev_mode is False
    assert settings.key_store == "keyring"


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(tmp_path / "custom"))
    monkeypatch.setenv("BUDGET_BUDDY_HOST", "0.0.0.0")
    monkeypatch.setenv("BUDGET_BUDDY_PORT", "9000")
    monkeypatch.setenv("BUDGET_BUDDY_DEV_MODE", "true")
    settings = Settings()
    assert settings.data_dir == tmp_path / "custom"
    assert settings.host == "0.0.0.0"
    assert settings.port == 9000
    assert settings.dev_mode is True


def test_default_data_dir_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert default_data_dir() == tmp_path / "BudgetBuddy"


def test_default_data_dir_other(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert default_data_dir() == tmp_path / ".local" / "share" / "budget-buddy"


def test_create_app_creates_data_dir(data_dir):
    assert not data_dir.exists()
    app = create_app()
    assert data_dir.is_dir()
    assert app.state.settings.data_dir == data_dir


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_data_dir_is_private_on_posix(data_dir):
    create_app()
    assert stat.S_IMODE(data_dir.stat().st_mode) == 0o700


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_existing_data_dir_is_tightened_on_posix(data_dir):
    data_dir.mkdir()
    os.chmod(data_dir, 0o755)
    create_app()
    assert stat.S_IMODE(data_dir.stat().st_mode) == 0o700


def test_api_docs_disabled_by_default(make_client, monkeypatch):
    monkeypatch.delenv("BUDGET_BUDDY_DEV_MODE", raising=False)
    client = make_client()
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_api_docs_enabled_in_dev_mode(make_client, monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_DEV_MODE", "true")
    client = make_client()
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200, path
