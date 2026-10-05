"""Warnings when the data folder is somewhere risky (issue #5)."""

import logging

import pytest

from app.data_folder import data_dir_warnings, warn_if_risky_data_dir
from app.main import create_app


def test_ordinary_folder_has_no_warnings(tmp_path):
    assert data_dir_warnings(tmp_path / "bb", environ={}) == []


def test_inside_a_git_repository(tmp_path):
    (tmp_path / "project" / ".git").mkdir(parents=True)
    [message] = data_dir_warnings(tmp_path / "project" / "data", environ={})
    assert "code project folder" in message


def test_onedrive_env_var(tmp_path):
    onedrive = tmp_path / "Synced"
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        [message] = data_dir_warnings(onedrive / "BudgetBuddy", environ={var: str(onedrive)})
        assert "OneDrive" in message


@pytest.mark.parametrize(
    ("folder", "service"),
    [
        ("OneDrive", "OneDrive"),
        ("OneDrive - Contoso", "OneDrive"),
        ("Dropbox", "Dropbox"),
        ("Dropbox (Family)", "Dropbox"),
        ("iCloudDrive", "iCloud Drive"),
        ("iCloud Drive", "iCloud Drive"),
        ("Google Drive", "Google Drive"),
        ("My Drive", "Google Drive"),
        ("dropbox", "Dropbox"),  # any capitalization
        ("Mobile Documents", "iCloud Drive"),  # ~/Library/Mobile Documents on macOS
        ("CloudStorage", "a cloud storage app"),  # ~/Library/CloudStorage on macOS
        ("Box", "Box"),
        ("pCloud Drive", "pCloud"),
        ("Nextcloud", "Nextcloud"),
    ],
)
def test_common_sync_folder_names(tmp_path, folder, service):
    [message] = data_dir_warnings(tmp_path / folder / "BudgetBuddy", environ={})
    assert service in message
    assert "Moving your data folder" in message


def test_similar_names_are_fine(tmp_path):
    assert data_dir_warnings(tmp_path / "MyDropboxNotes" / "bb", environ={}) == []


def test_startup_logs_warning(tmp_path, monkeypatch, caplog):
    data_dir = tmp_path / "Dropbox" / "BudgetBuddy"
    monkeypatch.setenv("BUDGET_BUDDY_DATA_DIR", str(data_dir))
    with caplog.at_level(logging.WARNING, logger="app.data_folder"):
        app = create_app()
    app.state.engine.dispose()
    records = [r for r in caplog.records if r.name == "app.data_folder"]
    assert len(records) == 1 and records[0].levelno == logging.WARNING
    assert "Dropbox" in records[0].getMessage()


def test_startup_quiet_for_normal_folder(data_dir, caplog):
    with caplog.at_level(logging.WARNING, logger="app.data_folder"):
        app = create_app()
    app.state.engine.dispose()
    assert [r for r in caplog.records if r.name == "app.data_folder"] == []


@pytest.mark.parametrize("folder", ["Documents", "Desktop"])
def test_macos_icloud_desktop_and_documents(tmp_path, folder):
    path = tmp_path / folder / "BudgetBuddy"
    [message] = data_dir_warnings(path, environ={}, platform="darwin", home=tmp_path)
    assert "iCloud Drive" in message
    assert data_dir_warnings(path, environ={}, platform="win32", home=tmp_path) == []


@pytest.mark.parametrize("error", [PermissionError("no access"), RuntimeError("symlink loop")])
def test_check_errors_never_stop_startup(tmp_path, monkeypatch, caplog, error):
    def boom(*args, **kwargs):
        raise error

    monkeypatch.setattr("app.data_folder.data_dir_warnings", boom)
    with caplog.at_level(logging.DEBUG, logger="app.data_folder"):
        warn_if_risky_data_dir(tmp_path / "bb", environ={})
    assert all(r.levelno < logging.WARNING for r in caplog.records if r.name == "app.data_folder")
    assert not any(str(tmp_path) in r.getMessage() for r in caplog.records)
