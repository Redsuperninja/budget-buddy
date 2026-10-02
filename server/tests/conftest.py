from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway data folder so tests never touch real user data."""
    path = tmp_path / "bb-data"
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(path))
    return path


@pytest.fixture
def client(data_dir: Path) -> TestClient:
    """Test client that looks like it's connecting from this computer."""
    return TestClient(create_app(), client=("127.0.0.1", 50000))
