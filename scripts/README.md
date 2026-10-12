# scripts/

What the double-click files in [`launch/`](../launch/) run, plus tools for testers, developers and releases, one folder
each so you can tell at a glance who a script is for. The PowerShell scripts are for Windows; the Python files are
small clients of the Home Base's this-computer-only API and never import the server.

## Everyone (`scripts\`)

| Script | What it does |
| --- | --- |
| `start.ps1` | Everyday start (what `launch\Start Budget Buddy.bat` runs): sets up or updates the Home Base when needed, starts it on your real data, opens the dashboard; says so if it's already running. `-NoBrowser` skips opening the browser. |
| `paths.ps1` | Shared by the others: paths, `Assert-Python` (3.12+), `Install-Part <dir> <extras>` (installs a part into its `.venv` only when its `pyproject.toml` or the extras changed; stamp in `.venv`) and `Install-HomeBase [-Dev]`. Scripts in a subfolder dot-source it as `"$PSScriptRoot\..\paths.ps1"`. |

## Testers (`scripts\testing\`)

| Script | What it does |
| --- | --- |
| `setup.ps1` | One-time install of the Home Base (with developer tools) and the phone app's tools. |
| `start-test-server.ps1` | Starts a TEST Home Base on port 8766 with its own data folder (`-Reset` starts over). |
| `load-demo-data.ps1` (`demo_data.py`) | Fills the empty test Home Base with made-up accounts, spending and paychecks (three months; everyday spending varies a little each month, so month-to-month charts have something to show). |
| `import-csv.ps1` (`import_csv.py`) | Previews a bank CSV (try `sample-bank-statement.csv`), then imports it after you confirm. |
| `pair-phone.ps1` (`pair_phone.py`) | Starts pairing and shows the QR code for the phone to scan. |
| `start-phone-app.ps1` | Starts the phone app for Expo Go. |
| `test-settings.ps1` | Test settings (port 8766, test data folder) on top of `paths.ps1`. |
| `_local_api.py` | `LocalApi(base).call(method, path, json=, body=, content_type=)`: sends the Origin header and write token, fetches the token once, raises `ApiError` with a plain-English reason (`NotRunning` if nothing answers). |
| `_testguard.py` | The test-only guard (below). |

Step-by-step instructions are in [set-up-for-testing.md](../docs/guide/set-up-for-testing.md) and
[start-a-test-session.md](../docs/guide/start-a-test-session.md).

### The test-only guard

The Python helpers talk only to `127.0.0.1` on the test port (8766) and refuse to run against the real Home Base
(port 8765). They also refuse unless `start-test-server.ps1` has made its marker file (`.budget-buddy-test-folder`)
in the test data folder, so made-up data can't end up in real data.

## Building and releasing (`scripts\release\`)

| Script | What it does |
| --- | --- |
| `build-desktop.ps1` | Builds the desktop app into `launch\Budget Buddy\` ([desktop architecture](../docs/dev/architecture/desktop.md)); `launch\Build desktop app.bat` runs it. |
| `install-desktop.ps1` | Installs the built app with `desktop\packaging\install.ps1` (the release download's installer): `%LOCALAPPDATA%\Programs\Budget Buddy`, Start menu and desktop shortcuts, an entry in Settings, Apps. `launch\Install desktop app.bat` runs it. |
| `make-release.ps1` | Builds the release download, `dist\Budget-Buddy-<version>-Windows.zip` and its `.sha256` ([release.md](../docs/dev/release.md)). |

## Developers (`scripts\dev\`)

| Script | What it does |
| --- | --- |
| `check-all.ps1` | Runs every part's checks, as CI does, and lists which passed ([testing.md](../docs/dev/testing.md)). |
| `tidy-branches.ps1` | Tidies local branches after their pull requests merge ([workflow.md](../docs/dev/workflow.md)). |
