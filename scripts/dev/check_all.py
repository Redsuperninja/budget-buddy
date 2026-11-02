"""Run every part's checks, the same ones CI runs, and say which passed. Use it before pushing or
merging, especially for a change in one part that others depend on (a route, the snapshot, the
desktop handshake).

    python3 scripts/dev/check_all.py      (on Windows, type py)

Each part must be set up once first (docs/dev/testing.md); a part that isn't is reported, not
skipped quietly. The desktop app is Windows-only, so it is skipped on other systems.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/, for _common

from _common import (  # noqa: E402
    DESKTOP_DIR,
    MOBILE_DIR,
    REPO,
    SERVER_DIR,
    WINDOWS,
    say,
    venv_python,
)

NOT_SET_UP = "NOT SET UP (see docs/dev/testing.md)"


def python_checks(python: Path, lint: str = ".", *tests: str) -> list[list]:
    """Lint, format check and tests with a part's own Python."""
    return [
        [python, "-m", "ruff", "check", lint],
        [python, "-m", "ruff", "format", "--check", lint],
        [python, "-m", "pytest", "-q", *tests],
    ]


def parts() -> list[tuple[str, Path, bool, list[list]]]:
    """(name, folder, set up?, commands) for each part."""
    server, desktop = venv_python(SERVER_DIR), venv_python(DESKTOP_DIR)
    node, npm, npx = (shutil.which(tool) for tool in ("node", "npm", "npx"))
    scripts = REPO / "scripts"
    return [
        ("Server", SERVER_DIR, server.exists(), python_checks(server)),
        ("Scripts", REPO, server.exists(), python_checks(server, "scripts", "scripts/tests")),
        ("Dashboard", REPO / "dashboard", bool(node), [[node, "--test"]]),
        (
            "Phone",
            MOBILE_DIR,
            bool(npx) and (MOBILE_DIR / "node_modules").is_dir(),
            [[npx, "tsc", "--noEmit"], [npm, "test", "--", "--silent"]],
        ),
        ("Desktop", DESKTOP_DIR, desktop.exists(), python_checks(desktop)),
        # Every dashboard page in a real (headless) browser, against a throwaway Home Base.
        # Nothing private (emails, user paths, public IPs, databases, keys) in tracked files.
        ("Public", REPO, True, [[sys.executable, scripts / "dev" / "check_public.py"]]),
        ("Pages", REPO, server.exists(), [[sys.executable, scripts / "dev" / "check_pages.py"]]),
    ]


def check(folder: Path, ready: bool, commands: list[list]) -> str:
    if not ready:
        return NOT_SET_UP
    for command in commands:
        if subprocess.run([str(part) for part in command], cwd=folder).returncode:
            return "FAILED: " + " ".join([Path(command[0]).stem, *map(str, command[1:])])
    return "passed"


def main() -> int:
    argparse.ArgumentParser(description="Run every part's checks.").parse_args()
    results = {}
    for name, folder, ready, commands in parts():
        if name == "Desktop" and not WINDOWS:
            results[name] = "skipped (the desktop app is Windows-only)"
            continue
        say(f"== {name}", "cyan")
        results[name] = check(folder, ready, commands)
    say()
    for name, result in results.items():
        say(f"{name:<10} {result}", "green" if result == "passed" else "yellow")
    return 0 if all(r == "passed" or r.startswith("skipped") for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
