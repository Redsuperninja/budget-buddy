"""Safety checks shared by the test helpers: only ever talk to the TEST Home Base.

start_test_server.py writes a marker file into the test data folder. The helpers refuse to run
unless that marker exists and they're pointed at the test port, so made-up data can't end up in a
real Home Base even if someone runs theirs on an unusual port.
"""

import os
import sys
from pathlib import Path

REAL_PORT = 8765
TEST_PORT = 8766
MARKER_NAME = ".budget-buddy-test-folder"


def test_data_dir() -> Path:
    """The TEST Home Base's own data folder, next to where the real one is kept by default
    (server/app/config.py). ``BUDGET_BUDDY_TEST_DATA_DIR`` moves it (check_pages.py uses a
    temporary folder)."""
    if override := os.environ.get("BUDGET_BUDDY_TEST_DATA_DIR"):
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "BudgetBuddy-Test"
    return Path.home() / ".local" / "share" / "budget-buddy-test"


def refuse_unless_test_server(port: int) -> str | None:
    """A plain-English reason to stop, or None if it's safe to go ahead."""
    if port == REAL_PORT:
        return (
            "Refusing: 8765 is the real Home Base's port. These helpers are for the test one only."
        )
    if port != TEST_PORT:
        return f"Refusing: the test Home Base runs on port {TEST_PORT}, not {port}."
    if not (test_data_dir() / MARKER_NAME).is_file():
        return (
            "Refusing: the test Home Base hasn't been started from "
            "scripts/testing/start_test_server.py yet. Start it there first (in its own window)."
        )
    return None
