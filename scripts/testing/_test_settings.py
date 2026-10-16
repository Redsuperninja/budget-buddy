"""Shared by the tester scripts: the shared helpers, and the commands they tell testers to run.

The test Home Base is kept completely apart from real use (_testguard.py has the folder and port):
  - its own data folder (its own encryption key in the password vault, too),
  - its own port (8766; the real Home Base uses 8765),
so demo data can never end up in your real data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/, for _common

from _common import SERVER_DIR, command_for, stop, venv_python  # noqa: E402

SET_UP = command_for("scripts/testing/set_up.py")
START_TEST_SERVER = command_for("scripts/testing/start_test_server.py")


def require_set_up() -> Path:
    """The Home Base's Python, or a plain message to run set_up.py first."""
    python = venv_python(SERVER_DIR)
    if not python.exists():
        stop(f"Budget Buddy isn't set up on this computer yet. Run {SET_UP} first.")
    return python
