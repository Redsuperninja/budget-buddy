import sys
from pathlib import Path

from app.config import Settings, default_data_dir
from app.main import create_app


def test_defaults(monkeypatch):
    for var in ("BUDGET_BUDDY_DATA_DIR", "BUDGET_BUDDY_HOST", "BUDGET_BUDDY_PORT"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings()
    assert settings.data_dir == default_data_dir()
    assert settings.host == "0.0.0.0"
    assert settings.port == 8765


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(tmp_path / "custom"))
    monkeypatch.setenv("BUDGET_BUDDY_HOST", "127.0.0.1")
    monkeypatch.setenv("BUDGET_BUDDY_PORT", "9000")
    settings = Settings()
    assert settings.data_dir == tmp_path / "custom"
    assert settings.host == "127.0.0.1"
    assert settings.port == 9000


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
