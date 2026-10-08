"""Startup checks on where the data folder is (issue #5).

Two risky places get a plain-English warning (Budget Buddy still starts):

- inside a git repository (such as this project's own folder), where data could be committed
  and pushed by accident;
- inside a cloud-synced folder (OneDrive, Dropbox, iCloud Drive, Google Drive), which uploads a
  copy of your data to someone else's servers and can corrupt a database that's open while it
  syncs.
"""

import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path

logger = logging.getLogger(__name__)

# Environment variables Windows and the OneDrive app set to the synced folder.
SYNC_FOLDER_ENV_VARS = ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")

# Folder names used by sync apps (compared case-insensitively).
_SYNC_FOLDER_NAMES = {
    "onedrive": "OneDrive",
    "dropbox": "Dropbox",
    "icloud drive": "iCloud Drive",
    "iclouddrive": "iCloud Drive",
    "mobile documents": "iCloud Drive",  # ~/Library/Mobile Documents on macOS
    "google drive": "Google Drive",
    "googledrive": "Google Drive",
    "my drive": "Google Drive",
    "cloudstorage": "a cloud storage app",  # ~/Library/CloudStorage on macOS
    "box": "Box",
    "pcloud drive": "pCloud",
    "nextcloud": "Nextcloud",
}

# On macOS, iCloud can sync Desktop and Documents ("Desktop & Documents Folders" setting).
_MACOS_ICLOUD_OPTIONAL = ("Desktop", "Documents")

MOVE_HELP = (
    'See "Moving your data folder" in docs/guide/move-your-data-folder.md for how to move it.'
)


def _sync_service(
    path: Path, environ: Mapping[str, str], platform: str = sys.platform, home: Path | None = None
) -> str | None:
    for var in SYNC_FOLDER_ENV_VARS:
        value = environ.get(var)
        if value:
            sync_root = Path(value).resolve()
            if path == sync_root or sync_root in path.parents:
                return "OneDrive"
    for part in path.parts:
        name = part.lower()
        if name in _SYNC_FOLDER_NAMES:
            return _SYNC_FOLDER_NAMES[name]
        # Work/school OneDrive folders are named like "OneDrive - Company Name".
        if name.startswith(("onedrive - ", "onedrive-")):
            return "OneDrive"
        if name.startswith("dropbox ("):  # "Dropbox (Team Name)"
            return "Dropbox"
    if platform == "darwin":
        home = Path.home() if home is None else home
        for name in _MACOS_ICLOUD_OPTIONAL:
            folder = home / name
            if path == folder or folder in path.parents:
                return "iCloud Drive (if Desktop & Documents syncing is turned on)"
    return None


def _git_repo_root(path: Path) -> Path | None:
    for folder in (path, *path.parents):
        if (folder / ".git").exists():
            return folder
    return None


def data_dir_warnings(
    data_dir: Path,
    environ: Mapping[str, str] | None = None,
    platform: str = sys.platform,
    home: Path | None = None,
) -> list[str]:
    """Plain-English warnings about where ``data_dir`` is. Empty if the location looks fine."""
    environ = os.environ if environ is None else environ
    path = Path(data_dir).resolve()
    warnings = []

    repo = _git_repo_root(path)
    if repo is not None:
        warnings.append(
            f"Your Budget Buddy data folder ({path}) is inside a code project folder ({repo}). "
            "Your financial data could be shared by accident if that project is uploaded. "
            f"Please move it somewhere else. {MOVE_HELP}"
        )

    service = _sync_service(path, environ, platform, home)
    if service is not None:
        warnings.append(
            f"Your Budget Buddy data folder ({path}) looks like it's inside {service}. That "
            "uploads a copy of your financial data to the internet, and syncing while Budget "
            "Buddy is running can damage the database. Please move it to a folder that isn't "
            f"synced. {MOVE_HELP}"
        )
    return warnings


def warn_if_risky_data_dir(data_dir: Path, environ: Mapping[str, str] | None = None) -> None:
    """Log the warnings. Never stops startup: an unreadable parent folder or a symlink loop
    (which Python 3.12 raises on) just skips the check."""
    try:
        messages = data_dir_warnings(data_dir, environ)
    except (OSError, RuntimeError):
        logger.debug("Couldn't check where the data folder is; skipping the location warning.")
        return
    for message in messages:
        logger.warning(message)
