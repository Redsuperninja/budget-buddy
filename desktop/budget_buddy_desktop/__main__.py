"""``python -m budget_buddy_desktop [--background | --window]``; also ``Budget Buddy.exe``."""

import os
import sys

from budget_buddy_desktop.launcher import main


def give_output_somewhere() -> None:
    """A windowed program has no console, but the window and tray libraries may still log."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")  # noqa: SIM115 (lives as long as the process)
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")  # noqa: SIM115


if __name__ == "__main__":
    give_output_somewhere()
    sys.exit(main(sys.argv[1:]))
