# Budget Buddy: technical overview

*For developers, reviewers and the technically curious. For the plain-English version, see the
[overview](overview.md). The authoritative details live in [docs/dev/](../dev/README.md) and the [ADRs](../adr/).*

## What it is

A local-first personal finance and tax-prep app. One computer at home runs the **Home Base** (an HTTP API over an
encrypted SQLite database). Everything else is a client of it: a no-build web dashboard, a Windows desktop shell,
phone browsers on the home network, and an Expo phone app that syncs over Wi-Fi. There is no cloud component and
no account system.

```
 ┌────────────────────────── Home network ──────────────────────────┐
 │                                                                  │
 │  Budget Buddy computer                                           │
 │  ┌──────────────────────────────┐        ┌────────────────────┐  │
 │  │ Desktop app (pywebview, tray)│ ─HTTP─▶│ Home Base           │  │
 │  │ or any browser on 127.0.0.1  │        │ FastAPI + SQLAlchemy│  │
 │  └──────────────────────────────┘        │ SQLite (encrypted   │  │
 │                                          │ columns + files)    │  │
 │  Phone / laptop browser ── joined with ─▶│                     │  │
 │  a one-time code, cookie (ADR-0009)      │ serves dashboard/   │  │
 │                                          │                     │  │
 │  Phone app (Expo) ── NaCl-boxed sync ───▶│                     │  │
 │  paired by QR (ADR-0002, ADR-0004)       └────────────────────┘  │
 └──────────────────────────────────────────────────────────────────┘
   Only optional outbound call: live prices from Finnhub (symbols only, ADR-0010)
```

## The parts

| Part | Stack | Notes |
| --- | --- | --- |
| `server/` Home Base | Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, SQLite | ~30 routers; migrations run automatically at start with a backup copy first |
| `dashboard/` | Plain HTML, CSS, ES modules. No framework, no bundler, no dependencies | Served by the Home Base; strict CSP (no inline script or style), SVG charts built in code |
| `desktop/` | Python, pywebview, pystray, PyInstaller | Starts the Home Base as a child process and proves it's genuine with an HMAC challenge before showing it |
| `mobile/` | Expo (React Native, TypeScript), tweetnacl | Offline snapshot, receipt capture, sync on home Wi-Fi |
| `scripts/`, `launch/` | PowerShell + small Python API clients | Double-click start, build, install and release; demo data for testers |

Parts never import each other's code; they meet only at the HTTP API or the [sync contract](../api/sync-contract.md)
([ADR-0005](../adr/0005-dashboard-own-folder.md)).

## Design choices worth a look

**Money and dates.** All money is integer cents end to end; the dashboard converts typed dollars with string logic,
never floats. Dates are ISO `YYYY-MM-DD`. Tax-year numbers (limits, standard deductions) live in per-year JSON files
with sources ([tax-data.md](../dev/tax-data.md)), not in code.

**Encryption at rest** ([ADR-0003](../adr/0003-encryption-at-rest.md)). One master key per data folder, kept in the
OS credential vault via `keyring`, never on disk. HKDF-SHA256 derives separate keys for fields and files; sensitive
columns and receipt photos use AES-256-GCM bound to where each value belongs. A recovery phrase can restore the key.

**Phone sync** ([ADR-0002](../adr/0002-wifi-qr-sync.md), [ADR-0004](../adr/0004-sync-contract-v1.md)). Pairing is a
QR code carrying a one-time code and a per-session X25519 public key; both sides derive a shared key and every
payload travels as a NaCl `secretbox` envelope with nonce and timestamp. The contract is versioned and has shared
test vectors that both the Python and TypeScript sides run.

**Browsers on the home network** ([ADR-0009](../adr/0009-other-computers.md)). Off until used. A one-time 8-character
code (hashed in memory only, five tries, rate-limited) issues an `HttpOnly`, `SameSite=Strict` cookie tied to the
joining address for 90 days. Joined devices get an allow-list of routes; pairing and device management stay on the
Budget Buddy computer. This is also how phones use the dashboard today.

**Web safety without a framework.** The page is built only with `createElement` and `textContent`. A static test
fails the build on `innerHTML`, inline script or style, any internet address, or a route string outside
`js/api/endpoints.js`. Writes need a per-run CSRF token and a matching `Origin`; a Host allow-list blocks DNS
rebinding.

**One UI, two audiences.** The dashboard starts in a *simple view*. Power-user pieces carry an `advanced` class
that CSS hides unless `<html data-view="all">`, set from the header's Settings menu and remembered per browser.
The API and data are identical in both views, so the switch is display-only and costs nothing to maintain. Under
40rem wide, the same CSS turns wide tables into stacked label/value cards (each cell carries its column name), so
phones get a usable layout from the same code.

**Domain logic that does real work.** A 50/30/20 suggested budget from recent months; auto-sort rules, including
ones learned from your own choices; transfer matching between your accounts (card payments, savings, retirement);
FIFO cost basis with short/long-term gains and possible wash-sale flags; dividend detection; retirement and HSA
limit tracking; and imports of bank CSVs, broker activity and positions, each previewed first and undoable from
import history. Changes to money or tax math need a domain review ([workflow.md](../dev/workflow.md)).

## Quality bar

| Part | Checks |
| --- | --- |
| Server | `ruff` lint and format, about 1,400 pytest tests (fake data, temporary folders, in-memory test key store), coverage floor 94% |
| Dashboard | `node --test` with no packages: safety rules on every file, 100% line, branch and function coverage of the logic modules |
| Desktop | `ruff`, pytest, 95% coverage floor; the window and tray are checked by hand |
| Phone | TypeScript strict, Jest with coverage thresholds, sync contract vectors |

Each part has its own CI workflow ([testing.md](../dev/testing.md)). Pushing a version tag builds the Windows
release on CI and attaches it to a draft GitHub Release ([release.md](../dev/release.md)).

## Shipping

- **Windows:** `scripts\make-release.ps1` makes `Budget-Buddy-<version>-Windows.zip`: the PyInstaller-built desktop
  app and Home Base (no Python needed), a per-user installer (no admin; Start menu, desktop shortcut, an entry in
  Settings, Apps), an uninstaller that keeps the data folder, and a plain-English read-me.
- **Phones:** the dashboard in the phone's browser for now; the Expo app runs in Expo Go during testing.
- **macOS/Linux:** run the Home Base from source ([README](../../README.md#quick-start)).

## How it's built

Every change is one small roadmap item on its own branch, built by Claude Code using specialized agents
(architect, backend, mobile, finance and tax, security, tests, docs, release) and reviewed by the owner. Storage,
crypto, pairing, sync and upload changes get a security review; budget or tax math gets a finance review. Docs ship in
the same branch as the code. See [workflow.md](../dev/workflow.md) and the [roadmap](../ROADMAP.md).
