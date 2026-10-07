"""Safety checks shared by the test helpers: only ever talk to the TEST Home Base.

start-test-server.ps1 writes a marker file into the test data folder. The helpers refuse to run
unless that marker exists and they're pointed at the test port, so made-up data can't end up in a
real Home Base even if someone runs theirs on an unusual port.
"""

import os
from pathlib import Path

REAL_PORT = 8765
TEST_PORT = 8766
MARKER_NAME = ".budget-buddy-test-folder"


def test_data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "BudgetBuddy-Test"


def refuse_unless_test_server(port: int) -> str | None:
    """A plain-English reason to stop, or None if it's safe to go ahead."""
    if port == REAL_PORT:
        return "Refusing: 8765 is the real Home Base's port. These helpers are for the test one only."
    if port != TEST_PORT:
        return f"Refusing: the test Home Base runs on port {TEST_PORT}, not {port}."
    if not (test_data_dir() / MARKER_NAME).is_file():
        return (
            "Refusing: the test Home Base hasn't been started from scripts\\start-test-server.ps1 yet. "
            "Start it there first (in its own window)."
        )
    return None


def csrf_token(base: str) -> str:
    """The Home Base's write token (it changes every time the Home Base starts)."""
    import json
    import urllib.request

    with urllib.request.urlopen(base + "/api/local/csrf-token", timeout=15) as response:
        return json.loads(response.read())["token"]
