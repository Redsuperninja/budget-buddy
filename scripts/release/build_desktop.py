"""Build the Windows desktop app into launch/Budget Buddy/ (roadmap 22, ADR-0008):
    Budget Buddy.exe            the window and tray icon (desktop/)
    home-base/                  the packaged Home Base it starts (server/, with the dashboard files)
Nobody needs Python to run the result. Then install_desktop.py adds it to the Start menu.

Each part is built in a new, empty venv (build/desktop/venv-<part>) from its
requirements-package.txt: the app's packages and PyInstaller, checked against their hashes
(ADR-0013). Nothing from a developer's .venv (test tools, the linter, packages left over from
older versions) ends up in the app.

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

from _version import version_info  # noqa: E402

from _common import (  # noqa: E402
    DESKTOP_DIR,
    LAUNCH_DIR,
    PACKAGE_LOCK,
    PACKAGING_DIR,
    REPO,
    SERVER_DIR,
    clean_env,
    install_locked,
    require_windows,
    run,
    say,
    stop,
)

WORK = REPO / "build" / "desktop"
# What Windows shows in each .exe's Properties, Details: {recipe: (exe name, description)}. The
# recipes read build/desktop/version-<recipe>.txt, written here from the one version (_version.py).
EXES = {
    "desktop": ("Budget Buddy", "Budget Buddy"),
    "home-base": ("Budget Buddy Home Base", "Budget Buddy Home Base"),
}


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


def fresh_venv(part_dir: Path, label: str) -> Path:
    """A new venv with only what ``part_dir`` runs on, plus PyInstaller. Returns its Python."""
    venv = WORK / f"venv-{part_dir.name}"
    shutil.rmtree(venv, ignore_errors=True)
    if venv.exists():  # a left-over package would end up in the app
        stop(f"Couldn't clear {venv}. Close anything using it, then try again.")
    say(f"Installing {label} into a new, empty folder (a minute or two)...")
    run([sys.executable, "-m", "venv", venv], REPO, f"Setting up {label} failed.", clean_env())
    python = venv / "Scripts" / "python.exe"
    install_locked(python, part_dir, PACKAGE_LOCK, label)
    return python


def write_version_info() -> None:
    for recipe, (exe_name, description) in EXES.items():
        text = version_info(exe_name, description)
        (WORK / f"version-{recipe}.txt").write_text(text, encoding="utf-8")


def pyinstaller(python: Path, spec: str, dist: Path) -> None:
    command = [python, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN"]
    command += ["--workpath", WORK, "--distpath", dist, PACKAGING_DIR / spec]
    run(command, REPO, f"Building {spec} failed.", clean_env())  # no PYTHONPATH code bundled


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

    WORK.mkdir(parents=True, exist_ok=True)
    server = fresh_venv(SERVER_DIR, "the Home Base packaging tools")
    desktop = fresh_venv(DESKTOP_DIR, "the desktop app tools")
    icon = WORK / "budget-buddy.ico"
    run(
        [desktop, "-m", "budget_buddy_desktop.icon", icon],
        REPO,
        "Drawing the icon failed.",
        clean_env(),
    )

    write_version_info()
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
