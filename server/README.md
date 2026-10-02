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

Developers changing the tables: edit `app/models/`, then generate a migration and check it by hand:

```powershell
.venv\Scripts\alembic revision --autogenerate -m "describe the change"
```

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
