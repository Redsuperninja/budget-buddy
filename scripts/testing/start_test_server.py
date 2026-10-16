"""Start a TEST Home Base with its own data folder and port, kept apart from any real data.
Leave this window open while testing; press Ctrl+C to stop.

    python3 scripts/testing/start_test_server.py           keep last time's test data
    python3 scripts/testing/start_test_server.py --reset   start over, empty
    (on Windows, type py instead of python3)
"""

import argparse
import shutil
import sys

from _test_settings import require_set_up
from _testguard import MARKER_NAME, TEST_PORT, test_data_dir

from _common import say, set_title, stop
from _processes import start_home_base, stopped_afterwards


def main() -> int:
    parser = argparse.ArgumentParser(description="Start a TEST Home Base with made-up data only.")
    parser.add_argument("--reset", action="store_true", help="clear the test data and start empty")
    reset = parser.parse_args().reset
    python = require_set_up()
    data, url = test_data_dir(), f"http://127.0.0.1:{TEST_PORT}"
    marker = data / MARKER_NAME

    if reset and data.exists():
        # Only ever a folder this script made (it has the marker). Paired test phones must
        # connect again.
        if not marker.is_file():
            stop(f"Not clearing {data}: it wasn't made by this script, so it may not be test data.")
        shutil.rmtree(data)
        say("Test data cleared.", "yellow")
    data.mkdir(parents=True, exist_ok=True)
    if not marker.is_file():
        marker.write_text(
            "Budget Buddy TEST data folder. Made-up data only. Safe to delete.\n", encoding="ascii"
        )

    set_title("Budget Buddy TEST Home Base")
    say()
    say("Budget Buddy TEST Home Base", "cyan")
    say(f"  Test data folder: {data}")
    say(f"  Open Budget Buddy:  {url}/   (type this into your browser)", "green")
    say(f"  Check it's running: {url}/api/health")
    say(f"  API explorer:       {url}/docs")
    say()
    if sys.platform == "win32":
        say(
            "If Windows asks whether to allow Python on networks, tick 'Private networks' "
            "only, never Public.",
            "yellow",
        )
        say("See 'Add a firewall rule' in docs/testing/set-up-for-testing.md.")
    elif sys.platform == "darwin":
        say(
            "If your Mac asks whether Python may accept incoming connections, choose Allow "
            "(phones need it).",
            "yellow",
        )
    say("Press Ctrl+C to stop.")
    say()

    settings = {
        "BUDGET_BUDDY_DATA_DIR": str(data),
        "BUDGET_BUDDY_PORT": str(TEST_PORT),
        "BUDGET_BUDDY_DEV_MODE": "true",  # turns on the API explorer page for testers
    }
    with stopped_afterwards(start_home_base(python, settings)) as server:
        return server.wait()
    return 0  # after Ctrl+C


if __name__ == "__main__":
    raise SystemExit(main())
