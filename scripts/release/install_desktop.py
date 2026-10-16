"""Install the desktop app built by build_desktop.py (launch/Budget Buddy/) for this Windows user,
with Start menu and desktop shortcuts. The work is done by packaging/windows/install.ps1, the same
installer the release download uses. Safe to run again to update.

    py scripts/release/install_desktop.py [--no-desktop-shortcut]
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/, for _common

from _common import LAUNCH_DIR, PACKAGING_DIR, require_windows, stop  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the built desktop app for this user.")
    parser.add_argument("--no-desktop-shortcut", action="store_true", help="Start menu only")
    no_desktop_shortcut = parser.parse_args().no_desktop_shortcut
    require_windows("The desktop app")
    built = LAUNCH_DIR / "Budget Buddy"
    if not (built / "Budget Buddy.exe").is_file():
        stop("Build the app first: double-click 'Build desktop app' in the launch folder.")
    installer = PACKAGING_DIR / "install.ps1"
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(installer)]
    command += ["-From", str(built)] + (["-NoDesktopShortcut"] if no_desktop_shortcut else [])
    return subprocess.run(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
