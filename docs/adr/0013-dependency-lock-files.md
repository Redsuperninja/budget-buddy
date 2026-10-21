# ADR-0013: Lock files with hashes for every Python install

**Status:** Accepted, 2026-10-17 (issue #6, part 2).

## Context
The Home Base and the desktop app list their packages in `pyproject.toml` with lower limits only
(`fastapi>=0.115`). Every install (Start Budget Buddy, the tester setup, CI, the release build) took whatever was
newest that day, unchecked: two computers could run different code, and a hijacked release would be installed as
soon as it was published. The scripts run on Windows, macOS and Linux ([ADR-0011](0011-cross-platform-scripts.md)),
so one lock file has to be right on all three.

| Tool to make the lock files | One file for every OS | Hashes | Extra tool to install |
| --- | --- | --- | --- |
| **uv (`uv pip compile --universal`)** | Yes, with markers like `sys_platform == 'win32'` | Yes | Only to update the files |
| pip-tools (`pip-compile`) | No: locks for the computer it runs on | Yes | Only to update the files |
| uv projects (`uv.lock`, `uv sync`) | Yes | Yes | On every computer that installs |

## Decision
**Each part has its lock files made by uv; installing them needs only pip** (the owner asked for the most reliable).
- `requirements-build.txt`: the build tool (setuptools), installed first. Some packages (the desktop app's
  `proxy-tools`) have no ready-made wheel and are built during the install; pip would otherwise fetch the
  newest setuptools for that, unchecked (found by the security review).
- `requirements.txt`: what the part needs to run. Start Budget Buddy uses it.
- `requirements-dev.txt`: plus every extra (tests, linter, PyInstaller), made with `-c requirements.txt` so shared
  packages have the same version. The tester setup and CI use it.
- `requirements-package.txt` (added later): `requirements.txt` plus only the packaging extra (PyInstaller), made
  with `-c requirements-dev.txt`. The release build installs it into a new, empty venv, so test tools and
  left-over packages never end up in the app.
- All four are made for Python 3.12 and newer, on every OS, with a hash for every file a version has on PyPI.
- `scripts/dev/lock_dependencies.py` writes them (`--upgrade` to move to newer versions). The first line holds the
  `pyproject.toml` hash; a test fails when a lock file is older than its `pyproject.toml`.
- Installing is `pip install --require-hashes -r requirements-build.txt`, then
  `pip install --require-hashes --no-build-isolation -r <file>`, then `pip install --no-deps --no-build-isolation -e .`,
  so nothing is downloaded or run unchecked. `scripts/_common.py:install_part` and CI do exactly this.
- Dependabot updates the lock files only (`versioning-strategy: lockfile-only`), at least a week after a release.

## Consequences
- Every computer installs the same versions, and a changed file on PyPI fails the install instead of running.
- Changing `pyproject.toml` means running the lock script in the same branch (the test says so).
- The tester setup also installs PyInstaller: one dev file per part is simpler than one per extra.
- `pip install --upgrade pip` is gone from installs: it downloaded pip unchecked, and Python's own pip is enough.
- uv is a developer tool only; nobody who just uses Budget Buddy needs it.
- A package that has to be built with something other than setuptools fails to install instead; we'd add its
  build tool to `requirements-build.txt`.
- The test checks each file's first line, not its body: a hand-edited pin would pass it, so lock-file changes
  in a PR are reviewed like code, and the files are only changed by the script or Dependabot.
