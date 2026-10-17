"""Open every dashboard page in a headless browser against a throwaway Home Base with demo data,
and fail on a script error, a file that didn't load, an error on the page, or an empty page.
Catches what file-reading tests can't, like a screen that breaks only when it runs. Needs Microsoft
Edge, Google Chrome or Chromium, and Node 22+.

    python3 scripts/dev/check_pages.py [--browser <path>] [--screenshots <folder>]

On Windows, type py instead of python3.

With --screenshots, it also saves the top of each page as <page>.png in that folder; the user
guide's pictures (docs/guide/images/) are made this way, from made-up demo data only.

Your real data and your own test data are never touched: everything lives in a new temporary
folder (with the encryption key in memory only) that is deleted afterwards. Uses the test port,
8766, so stop a test Home Base first.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / "testing")]  # for _common and _testguard

from _testguard import TEST_PORT  # noqa: E402

from _common import SERVER_DIR, WINDOWS, say, stop, venv_python  # noqa: E402
from _processes import health_ok, port_in_use, start, stop_tree  # noqa: E402

DEVTOOLS_PORT = 9333  # the browser's (check-pages.mjs)
HERE = Path(__file__).resolve().parent


def find_browser() -> str | None:
    """Edge or Chrome where they're usually installed, or Chromium on the path."""
    if WINDOWS:
        roots = [os.environ.get(n) for n in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
        places = [
            Path(root, *app)
            for root in roots
            if root
            for app in (
                ("Microsoft", "Edge", "Application", "msedge.exe"),
                ("Google", "Chrome", "Application", "chrome.exe"),
            )
        ]
    elif sys.platform == "darwin":
        places = [
            Path(f"/Applications/{app}.app/Contents/MacOS/{app}")
            for app in ("Google Chrome", "Microsoft Edge", "Chromium")
        ]
    else:
        names = (
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "microsoft-edge",
        )
        places = [Path(found) for name in names if (found := shutil.which(name))]
    return next((str(place) for place in places if place.is_file()), None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Open every dashboard page in a headless browser.")
    parser.add_argument("--browser", help="the browser program to use (default: Edge or Chrome)")
    parser.add_argument("--screenshots", type=Path, help="also save each page as a picture here")
    args = parser.parse_args()
    browser = args.browser or find_browser()
    python, node = venv_python(SERVER_DIR), shutil.which("node")
    if not browser:
        stop("Needs Microsoft Edge, Google Chrome or Chromium (or give one with --browser).")
    if not node:
        stop("Needs Node.js 22 or newer.")
    if not python.exists():
        stop("Set up the Home Base first (docs/dev/testing.md).")
    for port in TEST_PORT, DEVTOOLS_PORT:
        if port_in_use(port):
            stop(f"Something is already using port {port}. Stop it and try again.")

    run = Path(tempfile.mkdtemp(prefix="budget-buddy-check-pages-"))
    settings = {
        "BUDGET_BUDDY_TEST_DATA_DIR": str(run / "test-data"),
        "BUDGET_BUDDY_KEY_STORE": "memory",
        "BUDGET_BUDDY_INSECURE_TEST_KEYSTORE": "1",
        # The Home Base stops when this script does, even if it is killed outright.
        "BUDGET_BUDDY_STOP_WITH_PID": str(os.getpid()),
    }
    testing = SCRIPTS / "testing"
    server = checker = None
    try:
        with open(run / "server.log", "wb") as log:
            server = start(
                [python, testing / "start_test_server.py"], settings, background=True,
                stdout=log, stderr=subprocess.STDOUT,
            )  # fmt: skip
        deadline = time.monotonic() + 60
        while not health_ok(TEST_PORT):
            if server.poll() is not None or time.monotonic() > deadline:
                say((run / "server.log").read_text(errors="replace"))
                stop("The test Home Base didn't start; the messages above say why.")
            time.sleep(1)
        demo = subprocess.run(
            [python, testing / "load_demo_data.py"],
            env={**os.environ, **settings},
            capture_output=True,
            text=True,
        )
        if demo.returncode:
            stop(f"Loading the demo data failed:\n{demo.stdout}{demo.stderr}")
        base = f"http://127.0.0.1:{TEST_PORT}"
        command = [node, HERE / "check-pages.mjs", browser, base, run / "browser"]
        if args.screenshots:
            args.screenshots.mkdir(parents=True, exist_ok=True)
            command.append(args.screenshots.resolve())
        checker = start(command, {}, True)
        return checker.wait()
    finally:
        # Stop only what this run started (the browser is the checker's), then delete the folder.
        for process in checker, server:
            if process:
                stop_tree(process)
        time.sleep(1)
        shutil.rmtree(run, ignore_errors=True)
        if run.exists():  # a file still in use; only made-up data, its key was in memory only
            say(f"Couldn't delete {run} (made-up data only); delete it yourself.", "yellow")


if __name__ == "__main__":
    raise SystemExit(main())
