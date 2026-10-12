# Architecture

How Budget Buddy is put together. Each topic has its own page (below); this page is the big picture.

## Big picture

```
 ┌──────────────────── Your home network ─────────────────────┐
 │                                                             │
 │  ┌──────────────┐   encrypted sync    ┌──────────────────┐  │
 │  │  Home Base   │ ◀────────────────▶ │ Phone app         │  │
 │  │  (your PC)   │   (on home Wi-Fi)   └──────────────────┘  │
 │  │              │                     ┌──────────────────┐  │
 │  │ FastAPI      │ ◀── dashboard ───── │ Browser or desktop│  │
 │  │ SQLite DB    │     over HTTP       │ app on this PC;   │  │
 │  │ Receipt files│                     │ joined phones and │  │
 │  │ dashboard/   │                     │ computers         │  │
 │  └──────────────┘                     └──────────────────┘  │
 │   ← data lives here only                                    │
 └─────────────────────────────────────────────────────────────┘
   Nothing is sent to the internet or a cloud (except optional live prices: symbols only, ADR-0010).
```

## The parts and their boundaries

| Part | Folder | What it is | Talks to the others through |
| --- | --- | --- | --- |
| Home Base | `server/` | Python + FastAPI HTTP API, SQLite database, encrypted receipt files | (it is the hub) |
| Dashboard | `dashboard/` | Web page for the computer: plain HTML, CSS and JS, no build step | The server's HTTP API only ([ADR-0005](../../adr/0005-dashboard-own-folder.md)) |
| Phone app | `mobile/` | Expo (React Native + TypeScript), runs in Expo Go | The [sync contract](../../api/sync-contract.md) only ([ADR-0004](../../adr/0004-sync-contract-v1.md)) |
| Desktop app | `desktop/` | Windows app: the dashboard in a pywebview window, a light tray icon | Starts the Home Base as its own program; its HTTP API only ([ADR-0008](../../adr/0008-desktop-app.md)) |
| Scripts | `scripts/` | Everyday start, plus tester, release and developer tools (people double-click the wrappers in `launch/`) | The server's HTTP API only |
| Packaging | `packaging/` | Build recipes and the installer for the Windows download | No code of its own: reads `server/`, `dashboard/` and `desktop/` at build time |

Parts never import each other's code. When two parts need the same small helper (for example money
formatting), each keeps its own copy with its own tests, so one part can change without touching the others.

## Principles

- **Local only.** Data stays on the user's computer: no cloud, no analytics, no third-party calls with user
  data. The phone talks to the Home Base only on home Wi-Fi ([ADR-0001](../../adr/0001-local-first-stack.md),
  [ADR-0002](../../adr/0002-wifi-qr-sync.md)).
- **Encrypted at rest** where it matters ([ADR-0003](../../adr/0003-encryption-at-rest.md)); see
  [security.md](security.md).
- **Money is integer cents, dates are ISO `YYYY-MM-DD`.**
- **Tax-year numbers live in per-year data files** with sources ([../tax-data.md](../tax-data.md)), never in logic.
- **Every user-facing flow fits in one sentence.** The phone: *"Be home, open app, tap Sync."*
- **No personal defaults or secrets in the repo**; the data folder lives outside it.

## Topics

| Page | What it covers |
| --- | --- |
| [server.md](server.md) | Stack, data folder, startup, module map, the Local API's common rules |
| [desktop.md](desktop.md) | The Windows app: processes, light start, building the `.exe` |
| [dashboard.md](dashboard.md) | How the server finds and serves the dashboard, headers, CSRF, API-only mode |
| [phone-app.md](phone-app.md) | The phone app: offline snapshot, screens, reminders |
| [pairing.md](pairing.md) | Pairing a phone: server side, devices, home-network listener, phone side |
| [remote-computers.md](remote-computers.md) | Other computers on the home network: join codes, the cookie, what they may do |
| [sync.md](sync.md) | Syncing: server side (§4.4 order, limits, receipts), routes, phone side |
| [security.md](security.md) | Encryption at rest, what stays plain text, which routes face the network |
| [data-model.md](data-model.md) | Tables and key fields |
| [database.md](database.md) | Alembic migrations, automatic upgrade, backup copies |
| [ledger.md](ledger.md) | Accounts and transactions: kinds, signs, balances, routes |
| [budget-summary.md](budget-summary.md) | Categories and the monthly summary |
| [budget-engine.md](budget-engine.md) | Suggested budget (50/30/20 from recent months) |
| [category-rules.md](category-rules.md) | Auto-categorization rules |
| [csv-import.md](csv-import.md) | Bank CSV import |
| [imports.md](imports.md) | Import history and undoing an import |
| [activity-import.md](activity-import.md) | Brokerage activity files: transactions, trades and dividends sorted |
| [receipts.md](receipts.md) | Receipts and receipt photos |
| [paychecks.md](paychecks.md) | Paychecks, the adds-up rule, deposit links, year-to-date summary |
| [donations.md](donations.md) | Charitable donations and the yearly summary |
| [dividends.md](dividends.md) | Dividends found in transactions, their deposit sweeps |
| [transfers.md](transfers.md) | Matching transfers between your accounts automatically; transfer kinds |
| [stocks.md](stocks.md) | Stock lots, sales, FIFO, gains |
| [stock-import.md](stock-import.md) | Stock purchases and sales from a CSV file |
| [bank-trades.md](bank-trades.md) | Stock trades named in a bank file, their deposit sweeps, tickers remembered |
| [positions.md](positions.md) | Positions from a broker's file, compared with your trades |
| [investments.md](investments.md) | Holdings by account, typed-in prices, retirement and HSA limits |
| [tax-summary.md](tax-summary.md) | Other deductions, the yearly tax summary and its CSV export |

Wire format for the phone: [docs/api/sync-contract.md](../../api/sync-contract.md). Decisions: [docs/adr/](../../adr/).
