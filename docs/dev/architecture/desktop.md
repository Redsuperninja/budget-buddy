# Desktop app

Code: top-level `desktop/` (package `budget_buddy_desktop`, layout in [desktop/README.md](../../../desktop/README.md)).
Decision: [ADR-0008](../../adr/0008-desktop-app.md). Roadmap 22, 22b.

## Processes

```
 login (optional)            click "Open" / double-click the app
 ┌──────────────────┐        ┌───────────────────────────┐   starts, passes   ┌──────────────────────────┐
 │ Budget Buddy.exe │ spawns │ Budget Buddy.exe --window │ ─────────────────▶ │ Budget Buddy Home Base   │
 │   --background   │ ─────▶ │ pywebview window          │  STOP_WITH_PID     │ (server, own process)    │
 │ tray icon only   │        │ shows http://127.0.0.1:…  │ ◀── HTTP only ──── │ stops ~1 s after window  │
 └──────────────────┘        └───────────────────────────┘                    └──────────────────────────┘
```

- **Tray** (`--background`, or no options): one at a time (mutex `Local\\BudgetBuddyTray`). Loads no window
  library and starts nothing until opened. Opening starts a window process; if one it started is still open, it
  shows a "already open" note instead.
- **Window** (`--window`): starts its own Home Base and waits up to 60 seconds until that process is running and
  `/api/health` answers on the port (`BUDGET_BUDDY_PORT`, default 8765). If something already answers on the port,
  it shows it only if it proves it's Budget Buddy (`genuine.py`): the running Home Base keeps a random key in
  `home-base-running.json` in the private data folder (`server/app/instance_proof.py`), and the window sends a
  fresh nonce to `GET /api/local/instance/proof` (this computer only) and checks the HMAC-SHA256 answer. A
  look-alike can't read the data folder, so it's refused with a plain message. The desktop finds the data folder
  by the server's rule (`BUDGET_BUDDY_DATA_DIR`, else `%LOCALAPPDATA%\BudgetBuddy`); `genuine.data_dir` keeps a
  copy, since parts don't import each other. Both rules are written down in
  [desktop-handshake.md](../../api/desktop-handshake.md), whose example both sides' tests check. A reused Home Base (for example
  from `launch\Start Budget Buddy.bat`) keeps running when the window closes.
- **Home Base**: `server/.venv` `python -m app` from source, or `home-base\Budget Buddy Home Base.exe` beside the
  app. With `BUDGET_BUDDY_STOP_WITH_PID` it watches that process (`server/app/parent_watch.py`, through a handle
  opened at start-up, so a reused process ID can't fool it) and stops cleanly when it ends. Its output goes to the
  window process, which keeps the last 20 lines in memory only, to show a plain-English reason if starting fails
  (port in use, the server's own plain messages; anything else gets a general message). Nothing is logged to disk.
- **No financial data on disk:** every `/api/*` reply has `Cache-Control: no-store` (`server/app/network.py`), so
  neither a browser nor the window's storage (`%LOCALAPPDATA%\BudgetBuddy-Window`) keeps a copy.

- **Outside links** (Settings, About): the window gives the page one function, `open_link(url)`
  (`budget_buddy_desktop/links.py`, pywebview `js_api`). It opens the default browser only for
  `https://github.com/Redsuperninja/budget-buddy` and pages under it (no other host, port, user info, `..`
  or scheme). The page's links come from `GET /api/local/about`. If the window ever ends up on another site after
  loading, it goes back to the dashboard.

## Building

`scripts/release/build_desktop.py` (or `launch\Build desktop app.bat`) makes a new, empty venv per part in `build\desktop\`
(`venv-server`, `venv-desktop`) from its `requirements-package.txt` (the app's packages and PyInstaller, with hashes;
[ADR-0013](../../adr/0013-dependency-lock-files.md)), so no test tools or left-over packages from a developer's
`.venv` get bundled. It then draws the icon and runs both PyInstaller recipes
(`packaging/windows/desktop.spec`, `packaging/windows/home-base.spec`) into `launch\Budget Buddy\`. The Home Base
recipe bundles only the files the server serves (`index.html`, top-level CSS, `js/**/*.js`), the migrations and the
tax data. Both recipes leave out modules PyInstaller finds but the apps never run (each `excludes` list says why);
the desktop app keeps Pillow's font support (the icon's letter) and `ssl` (pywebview imports it on start). `scripts/release/install_desktop.py` copies the result (with `packaging/windows/install.ps1`) to `%LOCALAPPDATA%\Programs\Budget Buddy` and adds Start
menu and desktop shortcuts. `LICENSE` and `THIRD-PARTY-NOTICES.txt` (generated from the bundled packages' own licence files, see [release.md](../release.md)) go in the output too.
