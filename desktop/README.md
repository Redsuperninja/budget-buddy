# Desktop app (Windows)

Budget Buddy as a Windows app: the dashboard in its own window, and an optional light tray icon that starts
with Windows ([ADR-0008](../docs/adr/0008-desktop-app.md)). This part never imports the server's code: it starts
the Home Base as its own program and talks to it over its local address, like a browser does.

## Run it from source

```powershell
cd desktop
py -3 -m venv .venv
.venv\Scripts\pip install --require-hashes -r requirements-build.txt
.venv\Scripts\pip install --require-hashes --no-build-isolation -r requirements-dev.txt
.venv\Scripts\pip install --no-deps --no-build-isolation -e .
.venv\Scripts\python -m budget_buddy_desktop            # tray icon + window
.venv\Scripts\python -m budget_buddy_desktop --window   # just the window
```

It starts the server from `server\.venv`, so set that up first ([server/README.md](../server/README.md)).

## Build the .exe

Double-click **Build desktop app** in the [launch](../launch/) folder (or run `py scripts/release/build_desktop.py`). It makes
`launch\Budget Buddy\Budget Buddy.exe` plus `home-base\` (the packaged Home Base from
`packaging/windows/home-base.spec`). **Install desktop app** copies it to `%LOCALAPPDATA%\Programs\Budget Buddy` and
adds Start menu and desktop shortcuts.

## Make the release download

`py scripts/release/make_release.py` builds the app and packs it with `packaging\windows\install.ps1`, the two `.bat`
files and `READ ME FIRST.txt` beside it into `dist\Budget-Buddy-<version>-Windows.zip` ([release.md](../docs/dev/release.md)).

## Check it

```powershell
.venv\Scripts\ruff check . ; .venv\Scripts\ruff format --check . ; .venv\Scripts\pytest --cov
```

Coverage must stay at 95% or more (`pyproject.toml`). The real window and tray loop are checked by hand: open the
app, switch Colors, download the tax CSV, close the window (the Home Base stops within about a second), tick Start
with Windows on the tray icon and sign out and in again.

## Layout (`budget_buddy_desktop/`)

| File | Job |
| --- | --- |
| `__main__.py`, `launcher.py` | Entry point; picks tray, window, or both (`--background`, `--window`) |
| `tray.py` | The tray icon and its menu. Imports no window library and starts nothing until opened |
| `window.py` | The pywebview window showing the dashboard, and the start-up problem window |
| `home_base.py` | Starts the Home Base as its own program with `BUDGET_BUDDY_STOP_WITH_PID`, waits for it, reuses a running Budget Buddy that proves itself, explains failures |
| `probe.py` | Is a Home Base answering? (`/api/health`), and which port (`BUDGET_BUDDY_PORT`) |
| `genuine.py` | Is the Home Base already on the port really Budget Buddy? (challenge-response with the key in the data folder) |
| `commands.py` | Where this app and the Home Base are, from source or inside the `.exe` |
| `autostart.py` | Start with Windows (current user's Run key, no admin rights) |
| `single_instance.py` | One tray icon at a time (a named Windows mutex) |
| `icon.py` | The icon, drawn in code (`python -m budget_buddy_desktop.icon file.ico` saves the `.ico`) |
