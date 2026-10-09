"""Finds the dashboard folder and lists the files it may serve (ADR-0005).

The dashboard is a separate part of the repo (``dashboard/``), not a Python package. At startup this
module builds an allowlist: ``index.html``, the top-level ``*.css`` files and every ``*.js`` file
under ``js/``. Nothing else is reachable (not ``tests/``, ``package.json``, dotfiles or anything
outside the folder). Symlinks are never followed. If the folder is missing, the Home Base runs
API-only.
"""

import logging
import os
import stat
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("app.dashboard")

MAX_FILES = 200
RESCAN_SECONDS = 2.0  # a missing file triggers at most one rescan this often
MAX_FILE_BYTES = 1_000_000
CONTENT_TYPES = {".js": "text/javascript", ".css": "text/css"}


def default_dashboard_dir() -> Path:
    """``<repo>/dashboard``, found from this file (so it doesn't depend on the current folder).

    The packaged Home Base (``server/packaging/home-base.spec``) has the dashboard bundled in.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundle:
        return Path(bundle) / "dashboard"
    return Path(__file__).resolve().parents[2] / "dashboard"


@dataclass
class DashboardFiles:
    folder: Path  # resolved
    assets: dict[str, Path]  # URL path such as "js/main.js" -> file
    _rescanned_at: float = 0.0
    _rescan_lock: threading.Lock = field(default_factory=threading.Lock)

    def read_index(self) -> str | None:
        return self._read(self.folder / "index.html")

    def read_asset(self, name: str) -> str | None:
        path = self.assets.get(name)
        if path is None and self._rescan():
            path = self.assets.get(name)
        return self._read(path) if path else None

    def _rescan(self) -> bool:
        """Build the list again (same rules), at most every few seconds. An update can add files
        while Budget Buddy runs; without this, the new page would fail to load until a restart."""
        if not self._rescan_lock.acquire(blocking=False):
            return False  # another request is rescanning right now
        try:
            now = time.monotonic()
            if now - self._rescanned_at < RESCAN_SECONDS:
                return False
            self._rescanned_at = now
            try:
                assets = _find_assets(self.folder)
            except OSError:
                return False
            if len(assets) > MAX_FILES:
                return False
            self.assets = assets
            return True
        finally:
            self._rescan_lock.release()

    def _read(self, path: Path) -> str | None:
        # Checked again at request time, in case a file was swapped for a link since startup.
        if not _is_allowed(path, self.folder):
            return None
        try:
            with open(path, "rb") as handle:  # one open: what we check is what we read
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
                    return None
                data = handle.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                return None
            return data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return None


def _is_allowed(path: Path, folder: Path) -> bool:
    """A regular, single-link file that really sits inside the folder (no symlinks or junctions)."""
    try:
        if path.is_symlink() or not path.is_file():
            return False
        info = path.stat()
        if info.st_size > MAX_FILE_BYTES or info.st_nlink > 1:
            return False
        # A junction (Windows) or link in any parent folder makes the real path differ from
        # the path we built, so the two must match.
        resolved = path.resolve()
        return resolved.is_relative_to(folder) and resolved == folder / path.relative_to(folder)
    except (OSError, ValueError):
        return False


def _listed(path: Path, folder: Path) -> bool:
    return not path.name.startswith(".") and _is_allowed(path, folder)


def _is_plain_dir(path: Path, folder: Path) -> bool:
    try:
        return not path.is_symlink() and path.resolve() == folder / path.relative_to(folder)
    except (OSError, ValueError):
        return False


def _find_assets(folder: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for item in sorted(folder.glob("*.css")):
        if _listed(item, folder):
            found[item.name] = item
    js = folder / "js"
    if js.is_dir() and _is_plain_dir(js, folder):
        for root, _dirs, names in os.walk(js, followlinks=False):
            for name in sorted(names):
                path = Path(root) / name
                if path.suffix == ".js" and _listed(path, folder):
                    found[path.relative_to(folder).as_posix()] = path
    return found


def load_dashboard(folder: Path) -> DashboardFiles | None:
    """The files to serve, or ``None`` (API-only) when there is no usable dashboard folder."""
    try:
        resolved = folder.resolve()
        if not resolved.is_dir() or not _is_allowed(resolved / "index.html", resolved):
            raise FileNotFoundError
        assets = _find_assets(resolved)
    except OSError:
        log.warning("Dashboard files not found at %s. Running without the web page.", folder)
        return None
    if len(assets) > MAX_FILES:
        log.warning("Dashboard folder has too many files. Running without the web page.")
        return None
    return DashboardFiles(folder=resolved, assets=assets)
