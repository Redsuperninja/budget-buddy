# Budget Buddy Home Base (server)

The part of Budget Buddy that runs on your computer: Python 3.12+, FastAPI, SQLite. It never imports or packages
the dashboard; it serves the [`dashboard/`](../dashboard/README.md) folder if it finds one.

How it works: [docs/dev/architecture/](../docs/dev/architecture/README.md) (start with
[server.md](../docs/dev/architecture/server.md)). Settings: [docs/dev/settings.md](../docs/dev/settings.md).

## Set up (Windows, from this `server/` folder)

```powershell
py -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
```

On macOS/Linux use `python3 -m venv .venv` and `.venv/bin/...` instead.

## Run it

```powershell
.venv\Scripts\python -m app
```

Then open <http://127.0.0.1:8765/> for the dashboard. <http://127.0.0.1:8765/api/health> should show
`{"status": "ok", ...}`. If `dashboard/` is missing the server runs API only.

The first run makes the encryption key. Save the recovery phrase straight away, and restore it after
reinstalling Windows or moving computers ([security](../docs/dev/architecture/security.md)):

```powershell
.venv\Scripts\python -m app recovery-phrase show
.venv\Scripts\python -m app recovery-phrase restore
```

To try it with made-up data on a separate test Home Base (port 8766), use the [`scripts/`](../scripts/README.md).

## Check your work

```powershell
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .
.venv\Scripts\pytest
```

Tests keep the key in memory and use a fake dashboard folder: see [docs/dev/testing.md](../docs/dev/testing.md).
Changing tables: [docs/dev/architecture/database.md](../docs/dev/architecture/database.md).

## Layout (`app/`)

| Path | Job |
| --- | --- |
| `main.py`, `__main__.py`, `cli.py`, `serving.py` | Build the app, run it, recovery-phrase command line |
| `parent_watch.py` | Stop when the program that started us ends (`BUDGET_BUDDY_STOP_WITH_PID`, used by the desktop app) |
| `config.py` | Settings from environment variables |
| `services/`, `routers/`, `schemas/` | Business logic, thin routes, request and response shapes, grouped by area ([areas](../docs/dev/architecture/server.md#areas)) |
| `models/`, `migrations/`, `db.py` | Tables, Alembic migrations, engine |
| `crypto/` | Keys, encrypted columns and files, recovery phrase |
| `network.py`, `lan.py`, `listeners.py` | Access rules, home-network address and listener |
| `dashboard_files.py` | Finds the dashboard folder and its allowlist |
| `tax_data/` | Per-year tax numbers ([docs/dev/tax-data.md](../docs/dev/tax-data.md)) |

`packaging/windows/home-base.spec` (at the repo root) builds the packaged Home Base for the desktop app ([desktop.md](../docs/dev/architecture/desktop.md)).

The full module map is in [server.md](../docs/dev/architecture/server.md).

## API by area

Every `/api/local/...` route answers this computer, and joined computers on the home network (ADR-0009) except
for pairing and joining; common rules are in
[server.md](../docs/dev/architecture/server.md). With `BUDGET_BUDDY_DEV_MODE=true`, `/docs` lists every route.

| Area | Routes and rules |
| --- | --- |
| Accounts, transactions, transfers | [ledger.md](../docs/dev/architecture/ledger.md) |
| Other computers (join codes, `/api/remote/join`) | [remote-computers.md](../docs/dev/architecture/remote-computers.md) |
| Categories, monthly summary, budget plan | [budget-summary.md](../docs/dev/architecture/budget-summary.md) |
| Suggested budget | [budget-engine.md](../docs/dev/architecture/budget-engine.md) |
| Auto-categorization rules | [category-rules.md](../docs/dev/architecture/category-rules.md) |
| Bank CSV import | [csv-import.md](../docs/dev/architecture/csv-import.md) |
| Import history | [imports.md](../docs/dev/architecture/imports.md) |
| Brokerage activity import | [activity-import.md](../docs/dev/architecture/activity-import.md) |
| Receipts and photos | [receipts.md](../docs/dev/architecture/receipts.md) |
| Paychecks | [paychecks.md](../docs/dev/architecture/paychecks.md) |
| Donations | [donations.md](../docs/dev/architecture/donations.md) |
| Dividends | [dividends.md](../docs/dev/architecture/dividends.md) |
| Stocks | [stocks.md](../docs/dev/architecture/stocks.md) |
| Stock CSV import | [stock-import.md](../docs/dev/architecture/stock-import.md) |
| Positions file import | [positions.md](../docs/dev/architecture/positions.md) |
| Other deductions, yearly tax summary, CSV export | [tax-summary.md](../docs/dev/architecture/tax-summary.md) |
| Pairing, devices, home-network listener | [pairing.md](../docs/dev/architecture/pairing.md) |
| Phone sync (`/api/sync/*`) | [sync.md](../docs/dev/architecture/sync.md) and the [sync contract](../docs/api/sync-contract.md) |
| Dashboard pages, CSRF token | [dashboard.md](../docs/dev/architecture/dashboard.md) |
