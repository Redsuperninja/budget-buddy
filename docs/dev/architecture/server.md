# Home Base (server)

## Stack

Python 3.12+, **FastAPI** HTTP API, **SQLite** database, **SQLAlchemy** 2.x models, **Alembic** migrations,
Pydantic v2 schemas, pytest. Setup and run commands: [server/README.md](../../../server/README.md).

## Data folder

The data folder lives **outside the repo**: default `%LOCALAPPDATA%\BudgetBuddy` on Windows,
`~/.local/share/budget-buddy` elsewhere, or `BUDGET_BUDDY_DATA_DIR` ([settings](../settings.md)). Code in git
never contains personal data. It holds `budget.db`, its `.bak-<revision>` copies, encrypted receipt files under
`receipts/`, and the `key-fingerprint` file. On macOS/Linux the folder is made readable only by the user.
At startup the server warns if the folder sits inside a code project or a cloud-synced folder
(`app/data_folder.py`).

## Startup (`create_app()` in `app/main.py`)

1. Create the data folder and warn if it's in a risky place.
2. Load the encryption keys from the OS password vault, creating them on first run ([security.md](security.md)).
3. Open the database and upgrade it ([database.md](database.md)).
4. Remove orphaned receipt files left by a crash ([receipts.md](receipts.md)).
5. Purge ended pairing sessions (erasing their keys), load the server ID, detect the home-network address,
   find the dashboard folder ([dashboard.md](dashboard.md)), and make this run's CSRF token.
6. Add the middleware (home-network check, then Host/Origin/CSRF rules) and the routers.

`python -m app` also manages the home-network listener ([pairing.md](pairing.md)). `python -m app
recovery-phrase show|restore` is the recovery-phrase command line (`app/cli.py`).

## Module map (`server/app/`)

| Path | Job |
| --- | --- |
| `main.py`, `__main__.py`, `cli.py` | Build the app; run it; command line |
| `config.py` | Settings from environment variables ([settings](../settings.md)) |
| `db.py`, `migrations/` | Engine and Alembic migrations |
| `models/` | Tables: `ledger.py` (accounts, categories, category rules, transactions, CSV mappings, paychecks, receipts), `tax.py` (donations, stocks, deductions), `devices.py` (devices, pairing, nonces) |
| `schemas/` | Request and response shapes; `common.py` holds shared helpers such as `resolve_amount` |
| `routers/` | One per area; thin, no business logic |
| `services/` | Business logic, one module per area |
| `crypto/` | Keys, key stores, encrypted columns and files, recovery phrase, base64url |
| `network.py`, `lan.py`, `listeners.py` | Access rules middleware, home-network address, the second listener |
| `bodylimit.py`, `ratelimit.py`, `errors.py` | Streaming body limits, per-address rate limit, error shape |
| `money.py`, `shares.py` | Cents and share-quantity parsing |
| `dashboard_files.py` | Finds the dashboard folder and lists the files it may serve |
| `tax_data/` | Per-year tax data files and their loader ([../tax-data.md](../tax-data.md)) |
| `data_folder.py`, `logs.py`, `deps.py` | Data-folder warnings, logging, FastAPI dependencies |

## Local API: common rules

Every `/api/local/...` route (and the dashboard pages) follows these rules. Each area's routes are listed on its
own page ([ledger](ledger.md), [budget summary](budget-summary.md), [CSV import](csv-import.md),
[receipts](receipts.md), [paychecks](paychecks.md), [donations](donations.md), [stocks](stocks.md),
[pairing](pairing.md)).

- **This computer only.** Anything not from a loopback address gets 403 `not_this_computer`, except the phone's
  routes: `/api/health`, `/api/pair` and `/api/sync/*` ([security.md](security.md)).
- **Host allowlist.** Requests must be addressed to `127.0.0.1:{port}`, `localhost:{port}` or `[::1]:{port}`
  (plus the home-network address for the phone routes), else 403 `bad_host`. This stops DNS-rebinding pages.
- **Writes need a matching `Origin`** (`http://` plus one of those hosts) and the per-run CSRF token in
  `X-CSRF-Token`, else 403 `bad_origin` ([dashboard.md](dashboard.md)). No CORS headers are ever sent.
- **Money** goes in and out as whole cents (`*_cents`). Where a route allows it, dollar text (`"amount":
  "-12.34"`) may be sent instead, never both.
- **Errors** look like `{"error": {"code": "...", "message": "..."}}`, with plain-English messages.
- **`/docs`** (the API explorer) exists only with `BUDGET_BUDDY_DEV_MODE=true`.
