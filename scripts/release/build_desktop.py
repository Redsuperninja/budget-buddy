"""Build the Windows desktop app into launch/Budget Buddy/ (roadmap 22, ADR-0008):
    Budget Buddy.exe            the window and tray icon (desktop/)
    home-base/                  the packaged Home Base it starts (server/, with the dashboard files)
Nobody needs Python to run the result. Then install_desktop.py adds it to the Start menu.

    py scripts/release/build_desktop.py [--into <folder>]

--into builds into <folder>/Budget Buddy instead (for example to test a build while another one
runs). Windows only: the desktop app is a Windows app.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/, for _common

from _common import (  # noqa: E402
    DESKTOP_DIR,
    LAUNCH_DIR,
    PACKAGING_DIR,
    REPO,
    SERVER_DIR,
    install_part,
    require_windows,
    run,
    say,
    stop,
)

WORK = REPO / "build" / "desktop"


def running_from(folder: Path) -> bool:
    """True if Budget Buddy runs from ``folder``: Windows locks a running program's files, so
    building over it would fail half-way."""
    paths = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process -Name 'Budget Buddy','Budget Buddy Home Base' -ErrorAction SilentlyContinue"
         " | ForEach-Object Path"],
        capture_output=True, text=True,
    ).stdout.splitlines()  # fmt: skip
    return any(Path(path.strip()).is_relative_to(folder) for path in paths if path.strip())


def pyinstaller(python: Path, spec: str, dist: Path) -> None:
    command = [python, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN"]
    command += ["--workpath", WORK, "--distpath", dist, PACKAGING_DIR / spec]
    run(command, REPO, f"Building {spec} failed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Windows desktop app.")
    parser.add_argument("--into", type=Path, help="build into <folder>/Budget Buddy instead")
    into = parser.parse_args().into
    require_windows("The desktop app")
    dist = (into or LAUNCH_DIR).resolve()
    out = dist / "Budget Buddy"
    if running_from(out):
        stop(
            f"Budget Buddy is running from {out}. Close its window and choose Quit on its tray "
            "icon, then build again."
        )

    server = install_part(SERVER_DIR, ("package",), "the Home Base packaging tools")
    desktop = install_part(DESKTOP_DIR, ("build",), "the desktop app tools")
    WORK.mkdir(parents=True, exist_ok=True)
    icon = WORK / "budget-buddy.ico"
    run([desktop, "-m", "budget_buddy_desktop.icon", icon], REPO, "Drawing the icon failed.")

    say("Building Budget Buddy.exe and the Home Base (a few minutes)...")
    pyinstaller(desktop, "desktop.spec", dist)
    pyinstaller(server, "home-base.spec", out)
    shutil.copy(PACKAGING_DIR / "THIRD-PARTY-NOTICES.txt", out)

    say()
    say(f"Built: {out / 'Budget Buddy.exe'}", "green")
    say("Try it from there, or double-click 'Install desktop app' in the launch folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
