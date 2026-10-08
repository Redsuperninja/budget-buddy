"""Picks what to do from the command line: tray, window, or both (see ``budget_buddy_desktop``)."""

import argparse
import os
import sys
from pathlib import Path

from budget_buddy_desktop import commands, probe
from budget_buddy_desktop.single_instance import first_instance


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="Budget Buddy", add_help=False)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--background", action="store_true")
    mode.add_argument("--window", action="store_true")
    return parser.parse_args(argv)


def window_storage() -> Path:
    """The window's own browser storage (light/dark choice): beside Budget Buddy's data folder."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "BudgetBuddy-Window"


def run_window() -> int:
    """The window process: start this window's own Home Base, then show it."""
    from budget_buddy_desktop.home_base import HomeBase, StartFailed
    from budget_buddy_desktop.window import show_dashboard, show_problem

    home_base = HomeBase(probe.port())
    try:
        home_base.start()  # it stops by itself about a second after this program ends
    except StartFailed as problem:
        show_problem(str(problem))
        return 1
    show_dashboard(home_base.url, window_storage())
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse(sys.argv[1:] if argv is None else argv)
    if args.window:
        return run_window()
    with first_instance() as first:
        if not first:  # a tray icon is already showing: just open a window (nothing at login)
            if not args.background:
                commands.spawn("--window")
            return 0
        from budget_buddy_desktop.tray import Tray

        Tray(probe.port()).run(open_now=not args.background)
    return 0
