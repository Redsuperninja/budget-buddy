# ADR-0008: A desktop app: its own window, a light start at login

**Status:** Accepted, 2026-10-08 (built in roadmap 22 and 22b).

## Context
Today Budget Buddy runs as a server in a console window, and you use it in your web browser
([ADR-0001](0001-local-first-stack.md), [ADR-0005](0005-dashboard-own-folder.md)). Roadmap 22a made that a
double-click. The owner wants more:
- an **app of its own** (an `.exe` with its own window), not necessarily a web page in a browser;
- an option to **open at Windows start-up** that stays light, and only **fully starts when you open it**.

Ways to get a window of its own:

| Option | What it means | Reuses the dashboard? | Size / effort | License |
| --- | --- | --- | --- | --- |
| **pywebview** + PyInstaller | A native window that shows the existing dashboard using Windows' built-in Edge WebView2 | Yes, as is | Small; Python only | BSD (pywebview); PyInstaller's GPL has an exception that allows this use |
| Tauri | Rust app with a WebView2 window; runs the Python server beside it | Yes | Adds Rust and a second build | MIT/Apache |
| Electron | Bundles a whole Chromium | Yes | Large download (100+ MB) | MIT |
| Native toolkit (Qt / PySide, Tkinter) | Rebuild every screen | No, everything twice | Large; two UIs to keep in step | LGPL (Qt) / PSF |

## Decision
- **Its own part, `desktop/`** (the owner's call: it isn't part of the server). Like every part, it never
  imports another part's code. The window process starts the **Home Base as its own program** and uses it over
  `http://127.0.0.1:<port>`, exactly like a browser. It passes its process ID in `BUDGET_BUDDY_STOP_WITH_PID`, and
  the Home Base shuts itself down cleanly about a second after the app ends, even after a crash.
- **Two programs, one install folder**, built with PyInstaller: `Budget Buddy.exe` (desktop: window and tray)
  and `home-base\Budget Buddy Home Base.exe` (server, with the dashboard files bundled). Nobody needs Python. The
  browser keeps working too (same address).
- **Its own window through pywebview** (Edge WebView2, built into Windows), showing the existing dashboard, so
  there is one UI. The CSP, CSRF token and this-computer-only rules are unchanged. Downloads are allowed (the
  tax CSV). The window's own storage (the light/dark choice) is in `%LOCALAPPDATA%\BudgetBuddy-Window`; every
  API reply is `no-store`, so no financial data is cached there.
- **The window only shows its own Home Base.** If something else already answers on the port, it refuses rather
  than show a possible look-alike.
- **Light start at login (optional, off by default):** `Budget Buddy.exe --background` shows only the tray icon.
  It starts no Home Base, no database, no key and no window library until opened (about 50 MB, mostly Python
  itself). One tray at a time (a named mutex). Menu: Open, a status line (whether phones can sync now), Start
  with Windows, Quit. Closing the window stops the Home Base; the tray stays.
- **Start with Windows** is the current user's Run key (`HKCU\...\Run`, "Startup apps" in Settings): no admin
  rights, no service.
- **Everything people double-click lives in the top-level `launch/` folder** (start, build, install, and the
  built app in `launch\Budget Buddy\`). The PowerShell behind them stays in `scripts/`.

## Consequences
- `launch\Start Budget Buddy.bat` (22a) stays: it runs from source and uses the browser.
- New dependencies (pywebview, pystray, Pillow; PyInstaller to build) passed a `security-reviewer` review. They
  are version ranges for now; lock files are issue #6. pystray is LGPL-3.0, used unchanged as a separate package.
- An unsigned `.exe` triggers Windows SmartScreen. Code signing is part of public release prep (#25).
- Phones sync only while the window is open. An "always ready for my phone" option could come later.
- macOS/Linux keep the browser route for now.
