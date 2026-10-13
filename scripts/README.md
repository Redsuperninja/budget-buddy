# scripts/

Helpers for testers and developers. People double-click the wrappers in [`launch/`](../launch/). The PowerShell scripts are for Windows testers; the Python
files are small clients of the Home Base's this-computer-only API and never import the server.

| Script | For | What it does |
| --- | --- | --- |
| `start.ps1` | everyone | Everyday start (what `launch\Start Budget Buddy.bat` runs): sets up or updates the Home Base when needed, starts it on your real data, opens the dashboard; says so if it's already running. `-NoBrowser` skips opening the browser. |
| `paths.ps1` | all | Shared paths, `Assert-Python` (3.12+), `Install-Part <dir> <extras>` (installs a part into its `.venv` only when its `pyproject.toml` or the extras changed; stamp in `.venv`) and `Install-HomeBase [-Dev]`. |
| `build-desktop.ps1` | everyone | Builds the desktop app into `launch\Budget Buddy\` ([desktop architecture](../docs/dev/architecture/desktop.md)). |
| `install-desktop.ps1` | everyone | Installs the built app with `desktop\packaging\install.ps1` (the release download's installer): `%LOCALAPPDATA%\Programs\Budget Buddy`, Start menu and desktop shortcuts, an entry in Settings, Apps. |
| `make-release.ps1` | maintainers | Builds the release download, `dist\Budget-Buddy-<version>-Windows.zip` and its `.sha256` ([release.md](../docs/dev/release.md)). |
| `setup.ps1` | testers | One-time install of the Home Base (with developer tools) and the phone app's tools. |
| `start-test-server.ps1` | testers | Starts a TEST Home Base on port 8766 with its own data folder (`-Reset` starts over). |
| `start-phone-app.ps1` | testers | Starts the phone app for Expo Go. |
| `load-demo-data.ps1` (`demo_data.py`) | testers | Fills the empty test Home Base with made-up accounts, spending and paychecks (three months; everyday spending varies a little each month, so month-to-month charts have something to show). |
| `import-csv.ps1` (`import_csv.py`) | testers | Previews a bank CSV (try `sample-bank-statement.csv`), then imports it after you confirm. |
| `pair-phone.ps1` (`pair_phone.py`) | testers | Starts pairing and shows the QR code for the phone to scan. |
| `test-settings.ps1` | testers | Test settings (port 8766, test data folder) on top of `paths.ps1`. |
| `_local_api.py` | developers | `LocalApi(base).call(method, path, json=, body=, content_type=)`: sends the Origin header and write token, fetches the token once, raises `ApiError` with a plain-English reason (`NotRunning` if nothing answers). |
| `_testguard.py` | developers | The test-only guard (below). |

## The test-only guard

The Python helpers talk only to `127.0.0.1` on the test port (8766) and refuse to run against the
real Home Base (port 8765). They also refuse unless `start-test-server.ps1` has made its marker file
(`.budget-buddy-test-folder`) in the test data folder, so made-up data can't end up in real data.

Step-by-step instructions for testers are in `docs/guide/set-up-for-testing.md` and `docs/guide/start-a-test-session.md`.
