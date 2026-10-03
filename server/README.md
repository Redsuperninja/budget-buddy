# Budget Buddy Home Base (server)

The part of Budget Buddy that runs on your computer. Python 3.12+ and FastAPI.

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

Then open <http://127.0.0.1:8765/api/health>. You should see `{"status": "ok", ...}`.

## Check your work

```powershell
.venv\Scripts\ruff check .
.venv\Scripts\pytest
```

## Database

Your data is kept in one file, `budget.db`, inside the data folder. The Home Base creates it and
brings it up to date every time it starts, so there's nothing to set up. On macOS/Linux the file
is readable only by your user account.

Before an update changes an existing database, a copy is saved next to it as
`budget.db.bak-<number>`. You can delete old copies once Budget Buddy is working.

Developers changing the tables: edit `app/models/`, then generate a migration and check it by hand:

```powershell
.venv\Scripts\alembic revision --autogenerate -m "describe the change"
```

## Local API (for the computer-side dashboard)

Every route answers this computer only (anything else gets 403 `not_this_computer`), except the
phone's routes: `/api/health`, and later `/api/pair` and `/api/sync/*`. Requests must also be
addressed to `127.0.0.1:{port}`, `localhost:{port}` or `[::1]:{port}` (else 403 `bad_host`), and
anything that changes data must come with an `Origin` of `http://` plus one of those (else 403
`bad_origin`). These checks stop other websites open in your browser from reaching your data. Money goes in and out as whole cents (`amount_cents`); when creating or
editing a transaction you may send `amount` as dollar text (`"-12.34"`) instead. Errors look like
`{"error": {"code": "...", "message": "..."}}`. With dev mode on, `/docs` lists every route.

- Accounts: `GET/POST /api/local/accounts`, `GET/PATCH/DELETE /api/local/accounts/{id}`.
  `balance_cents` is the sum of the account's transactions (record a starting balance as an
  `adjustment`). Adjustments (including opening balances) change balances but are never counted
  as income or spending, so they can't have a category. A `refund` must be a positive amount. An
  account with transactions can't be deleted.
- Transactions: `GET/POST /api/local/transactions` (filters: `account_id`, `category_id`,
  `date_from`, `date_to`, `kind`, `q`, `limit`, `offset`; newest first),
  `GET/PATCH/DELETE /api/local/transactions/{id}`, and `POST/DELETE
  /api/local/transactions/{id}/transfer` to link or unlink a transfer between two of your accounts.
  Only two regular (`normal`) transactions can be linked; both move to the Transfer category. While
  linked, a transaction's account, amount, kind and category are locked and it can't be deleted:
  remove the link first.

## Settings

All optional, set as environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `BUDGET_BUDDY_DATA_DIR` | `%LOCALAPPDATA%\BudgetBuddy` (Windows), `~/.local/share/budget-buddy` (others) | Where your data is kept. Never inside this repo. |
| `BUDGET_BUDDY_HOST` | `127.0.0.1` | Network address to listen on. The default means "this computer only". |
| `BUDGET_BUDDY_PORT` | `8765` | Port to listen on. |
| `BUDGET_BUDDY_DEV_MODE` | `false` | Set to `true` to turn on the API explorer at `/docs` (for developers). |

On macOS/Linux the data folder is made readable only by your user account.

## Letting your phone connect (later)

Until phone pairing is ready, the Home Base only listens to this computer. When you want your
phone to reach it over your home Wi-Fi, start it like this:

```powershell
$env:BUDGET_BUDDY_HOST = "0.0.0.0"
.venv\Scripts\python -m app
```

The first time, Windows Firewall will ask whether to allow Python on networks. Tick
**Private networks** only. Leave **Public networks** unticked, so the Home Base stays hidden on
coffee-shop or airport Wi-Fi.

Even then, the server only answers requests from this computer or your home network; anything
else gets "403 Forbidden".
