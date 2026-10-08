# ADR-0008: A desktop app: its own window, a light start at login

**Status:** Proposed, 2026-10-07. Direction from the owner; the library choices need a check before building.

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

## Decision (proposed)
- **One app, `Budget Buddy.exe`, built with PyInstaller.** It contains the Home Base and the dashboard files. Nobody
  needs Python installed. The browser keeps working too (same address) for anyone who prefers it.
- **Its own window through pywebview.** It shows the existing dashboard, so there is one UI to maintain. The
  dashboard's safety rules (CSP, CSRF token, this-computer-only) stay as they are, since the window loads the
  same local address.
- **Light start at login (optional, off by default):** a tray icon starts with Windows. Until you open it, it does
  almost nothing: **no database, no encryption key loaded, no web server, no home-network listener.** Clicking the
  icon (or opening the app) starts the Home Base, which takes a second or two, then shows the window. Closing the
  window keeps it running in the tray, or quits, whichever the user picks in Settings. The tray menu has Open,
  Connect phone, Start with Windows (on/off) and Quit.
- **Phones:** a phone can only sync while the Home Base is fully running. The phone already says when it can't
  reach the computer; the tray shows a "Phones can sync now" state when it's running. An "always ready for my
  phone" setting can start everything at login for people who want that.
- **Start with Windows** uses the current user's Startup entry (no admin rights, no service).

## Consequences
- Replaces the console window from 22a for everyday users. `Start Budget Buddy.bat` stays for developers and
  testers.
- New dependencies (pywebview, a tray library such as pystray, PyInstaller) need a `security-reviewer` pass and
  pinned versions (issue #6). Check each license before adding it (pystray is LGPL, which is fine for a separate
  Python package but should be noted).
- An unsigned `.exe` triggers Windows SmartScreen warnings. Code signing is part of public release prep (#25).
- The light state must be tested so that a locked, idle tray icon never holds the decrypted key.
- macOS/Linux keep the browser route for now.
