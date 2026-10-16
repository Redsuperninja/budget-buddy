"""The test-only guard: made-up data can only ever go into a test folder."""

import tempfile
from pathlib import Path

import _testguard
import pytest


def test_the_test_folder_can_be_moved_inside_the_temporary_folder(monkeypatch):
    inside = Path(tempfile.gettempdir()) / "budget-buddy-check-pages-x" / "test-data"
    monkeypatch.setenv("BUDGET_BUDDY_TEST_DATA_DIR", str(inside))
    assert _testguard.test_data_dir() == inside.resolve()


def test_the_test_folder_can_never_be_moved_elsewhere(monkeypatch):
    # Such as the real data folder, left set in a terminal.
    monkeypatch.setenv(
        "BUDGET_BUDDY_TEST_DATA_DIR", str(Path.home() / ".local" / "share" / "budget-buddy")
    )
    with pytest.raises(SystemExit, match="must be inside the temporary folder"):
        _testguard.test_data_dir()


def test_the_real_port_is_refused():
    assert "real Home Base" in _testguard.refuse_unless_test_server(_testguard.REAL_PORT)


def test_a_folder_without_the_marker_is_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("BUDGET_BUDDY_TEST_DATA_DIR", str(tmp_path))
    assert "hasn't been started" in _testguard.refuse_unless_test_server(_testguard.TEST_PORT)
    (tmp_path / _testguard.MARKER_NAME).write_text("")
    assert _testguard.refuse_unless_test_server(_testguard.TEST_PORT) is None
