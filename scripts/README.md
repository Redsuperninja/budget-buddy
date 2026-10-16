# scripts/

What the double-click files in [`launch/`](../launch/) run, plus tools for testers, developers and releases, one folder
each so you can tell at a glance who a script is for. The scripts are Python (standard library only) and work the
same on Windows, macOS and Linux ([ADR-0011](../docs/adr/0011-cross-platform-scripts.md)). Run them from the Budget
Buddy folder: `python3 scripts/<script>.py` (on Windows, `py scripts\<script>.py`); `--help` lists each one's options.
The Python files in `testing/` are small clients of the Home Base's this-computer-only API and never import the server.

## Everyone (`scripts/`)

| Script | What it does |
| --- | --- |
| `start.py` | Everyday start (what **Start Budget Buddy** in `launch/` runs): sets up or updates the Home Base when needed, starts it on your real data, opens the dashboard; says so if it's already running. `--no-browser` skips opening the browser. |
| `run-python.sh`, `run-python.bat` | Find Python 3.12+ and run a script with it, from the Budget Buddy folder; the files in `launch/` call them (`.sh` on macOS and Linux, `.bat` on Windows). |
| `_common.py` | Shared by the others: paths, `say` / `stop` (plain-English messages, in color when the window can), the Python 3.12 check (on import), `venv_python(dir)`, `install_part(dir, extras, label)` (installs a part into its `.venv` only when its `pyproject.toml` or the extras changed; stamp in `.venv`) and `install_home_base(dev=)`. A script in a subfolder puts `scripts/` on `sys.path` first. |
| `_processes.py` | `start_home_base`, `wait_until_up`, `health_ok`, `port_in_use`, `stop_tree` and `stopped_afterwards`: run a Home Base and stop only what the script started, also after Ctrl+C. Each Home Base it starts stops by itself when the script ends (`BUDGET_BUDDY_STOP_WITH_PID`). |
| `tests/` | Tests for the shared helpers: `server/.venv/Scripts/pytest scripts/tests` (`server/.venv/bin/pytest` on macOS and Linux). `ruff.toml` lints `scripts/` in the server's style. |

## Testers (`scripts/testing/`)

| Script | What it does |
| --- | --- |
| `set_up.py` | One-time install of the Home Base (with developer tools) and the phone app's tools (needs Node.js). |
| `start_test_server.py` | Starts a TEST Home Base on port 8766 with its own data folder (`--reset` starts over). |
| `load_demo_data.py` | Fills the empty test Home Base with made-up accounts, spending and paychecks (three months; everyday spending varies a little each month, so month-to-month charts have something to show). |
| `import_csv.py` | Previews a bank CSV (by default `sample-bank-statement.csv`), then imports it after you confirm. `--account`, `--flip-sign`, `--skip-invalid`. |
| `pair_phone.py` | Starts pairing and shows the QR code for the phone to scan (runs itself with the Home Base's Python, which has the QR code tool). |
| `start_phone_app.py` | Starts the phone app for Expo Go. |
| `_test_settings.py` | Shared by the scripts above: puts `scripts/` on the path for `_common`, `require_set_up()`, and the commands they tell testers to run. |
| `_local_api.py` | `LocalApi(base).call(method, path, json=, body=, content_type=)`: sends the Origin header and write token, fetches the token once, raises `ApiError` with a plain-English reason (`NotRunning` if nothing answers). |
| `_testguard.py` | The test-only guard (below), and the test data folder: `%LOCALAPPDATA%\BudgetBuddy-Test` on Windows, `~/.local/share/budget-buddy-test` elsewhere, or `BUDGET_BUDDY_TEST_DATA_DIR`. |

Step-by-step instructions are in [set-up-for-testing.md](../docs/testing/set-up-for-testing.md) and
[start-a-test-session.md](../docs/testing/start-a-test-session.md).

### The test-only guard

The Python helpers talk only to `127.0.0.1` on the test port (8766) and refuse to run against the real Home Base
(port 8765). They also refuse unless `start_test_server.py` has made its marker file (`.budget-buddy-test-folder`)
in the test data folder, so made-up data can't end up in real data.

## Building and releasing (`scripts\release\`)

| Script | What it does |
| --- | --- |
| `build-desktop.ps1` | Builds the desktop app into `launch\Budget Buddy\` ([desktop architecture](../docs/dev/architecture/desktop.md)); `launch\Build desktop app.bat` runs it. |
| `install-desktop.ps1` | Installs the built app with `packaging\windows\install.ps1` (the release download's installer): `%LOCALAPPDATA%\Programs\Budget Buddy`, Start menu and desktop shortcuts, an entry in Settings, Apps. `launch\Install desktop app.bat` runs it. |
| `make-release.ps1` | Builds the release download, `dist\Budget-Buddy-<version>-Windows.zip` and its `.sha256` ([release.md](../docs/dev/release.md)). |

## Developers (`scripts/dev/`)

| Script | What it does |
| --- | --- |
| `check_all.py` | Runs every part's checks, as CI does, plus the scripts' lint (`ruff.toml`) and tests (`tests/`), and lists which passed ([testing.md](../docs/dev/testing.md)). Skips the Windows-only desktop app elsewhere. |
| `check_pages.py` (`check-pages.mjs`) | Opens every dashboard page in headless Edge, Chrome or Chromium (`--browser` to pick one) against a throwaway Home Base with demo data (temporary folder, deleted after), and fails on a script error, a file that didn't load, an error on the page or an empty page. `check_all.py` runs it too. |
| `tidy_branches.py` | Tidies local branches after their pull requests merge (`--apply` to do it; [workflow.md](../docs/dev/workflow.md)). Run it inside the repo. |
