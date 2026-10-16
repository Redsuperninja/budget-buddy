"""Start Budget Buddy for everyday use: sets itself up the first time, starts the Home Base, and
opens the dashboard in your browser. Close this window (or press Ctrl+C) to stop Budget Buddy.

    Double-click "Start Budget Buddy" in the launch folder, or run from the Budget Buddy folder:
    python3 scripts/start.py [--no-browser]          (on Windows, type py instead of python3)

Uses your real data folder and port 8765 (or BUDGET_BUDDY_DATA_DIR / BUDGET_BUDDY_PORT if set).
Testers with made-up data use scripts/testing/start_test_server.py instead.
"""

import argparse
import os
import webbrowser

from _common import install_home_base, say, set_title, stop
from _processes import health_ok, start_home_base, stopped_afterwards, wait_until_up


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Budget Buddy and open it in your browser.")
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    no_browser = parser.parse_args().no_browser
    port = os.environ.get("BUDGET_BUDDY_PORT") or "8765"
    url = f"http://127.0.0.1:{port}/"

    set_title("Budget Buddy")
    say("Budget Buddy", "cyan")
    if health_ok(port):
        say(f"Budget Buddy is already running. Opening it in your browser: {url}", "green")
        if not no_browser:
            webbrowser.open(url)
        return 0

    python = install_home_base()
    say("Starting... your data stays on this computer.")
    with stopped_afterwards(start_home_base(python, {})) as server:
        if not wait_until_up(port, server):
            stop(
                "Budget Buddy didn't start. The messages above say why. If another program "
                f"uses port {port}, close it or set BUDGET_BUDDY_PORT."
            )
        say()
        say(f"Budget Buddy is running: {url}", "green")
        say("Keep this window open while you use it. Close it, or press Ctrl+C, to stop.")
        say()
        if not no_browser:
            webbrowser.open(url)
        server.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
