# ADR-0011: Scripts in Python, with thin launchers for each system

**Status:** Accepted, 2026-10-16 (roadmap 22c).

## Context
Everything in `scripts/` was PowerShell, and the double-click files in `launch/` were `.bat` files that ran it. That
works only on Windows, yet the Home Base, the dashboard and the phone tools already run on macOS and Linux. The
owner asked for the scripts to work on Unix and to be easy for people on every system.

| Option | Windows double-click | macOS / Linux | Copies of each script |
| --- | --- | --- | --- |
| Keep PowerShell | Yes | Needs PowerShell installed | 1 |
| Rewrite in bash | Needs Git Bash or WSL | Yes | 1 |
| Bash and PowerShell side by side | Yes | Yes | 2, kept in step by hand |
| **Python, with thin launchers** | Yes (`.bat`) | Yes (`.sh`, `.command`) | 1 |

Budget Buddy already needs Python 3.12 or newer on every system, and Python's standard library covers everything
the scripts do: virtual environments, starting and stopping processes, HTTP checks, zip files, hashes.

## Decision
**The scripts are Python, standard library only; launchers just find Python and run them** (the owner's choice).
- `scripts/**/*.py` hold all the logic, once. Shared code is `scripts/_common.py` (paths, plain-English messages,
  the Python version check, installing a part into its `.venv` only when its `pyproject.toml` changed) and
  `scripts/_processes.py` (waiting for a Home Base, and stopping only what a script started).
- `scripts/run-python.sh` (macOS, Linux) and `scripts/run-python.bat` (Windows) find Python 3.12+ and run a script.
  The double-click files in `launch/` are one or two lines that call them: `.bat` for Windows, `.command` for
  macOS (double-click in Finder), `.sh` for Linux.
- Testers and developers type the same command everywhere: `python3 scripts/...` (on Windows, `py scripts\...`).
- A Home Base a script starts gets `BUDGET_BUDDY_STOP_WITH_PID` (the script's process), so it stops cleanly if the
  window is closed, on every system.
- **Stays Windows-only, in PowerShell:** `packaging/windows/install.ps1` and its `.bat` files. They ship inside the
  Windows download, where Python isn't installed, and they write Windows shortcuts and the Settings, Apps entry.
  The desktop app itself stays Windows-only ([ADR-0008](0008-desktop-app.md)); its build scripts are Python, but
  refuse to run on other systems.

## Consequences
- One copy of each script; macOS and Linux users get the same start, testing and developer tools as Windows.
- A Python script can't run before Python is installed, so the version check is in two places: the launchers (for
  "no Python at all") and `_common.py` (for "Python too old").
- `.sh` and `.command` files need the executable bit and LF line endings in git (`.gitattributes`), or macOS and
  Linux refuse to run them.
- The scripts are linted (`scripts/ruff.toml`, the server's style) and their shared helpers tested
  (`scripts/tests/`), on every system.
- Tester guides show both commands (`python3` and `py`) where they differ.
