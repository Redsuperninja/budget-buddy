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

## Encryption and your recovery phrase

Account numbers, notes, and receipt photos are encrypted. The key is kept in your computer's
password vault (Windows Credential Manager, the macOS Keychain, or a Linux Secret Service), never
in the data folder.

**Not everything is encrypted yet.** Amounts, dates, descriptions, shop, employer and charity
names are **not** encrypted, so anyone with a copy of the data folder can still read your
spending, pay and giving history. Keep the data folder out of cloud-synced folders (OneDrive,
Dropbox, iCloud and similar) and protect your Windows account with a password. What stays plain
text today, in `budget.db`:

- every amount and date, and each transaction's description
- shop names on receipts (`receipts.merchant`)
- employer names and gross/net pay on paychecks (`paychecks.employer`)
- account names and banks (`accounts.name`, `accounts.institution`)
- charity names on donations (`donations.organization`)
- stock symbols and lots

These stay readable so Budget Buddy can search, sort and add them up. Encrypting more of them,
or the whole database, is tracked in
[issue #28](https://github.com/Redsuperninja/budget-buddy/issues/28).

The first time Budget Buddy starts it makes the key. **Save your recovery phrase right away**:

```powershell
.venv\Scripts\python -m app recovery-phrase show
```

It asks you to type `SHOW` first, and only prints the phrase in a terminal window (not into a
file), after checking it really is the key for your data folder.

Write it on paper or keep it in a password manager. If the password vault is ever lost (for
example after reinstalling Windows or moving to a new computer), put the key back with:

```powershell
.venv\Scripts\python -m app recovery-phrase restore
```

Without the phrase, a lost key means the encrypted data can't be recovered. Backup copies named
`budget.db.bak-0001` or `-0002` were made before encryption existed and are not encrypted; Budget
Buddy tells you about them so you can delete them.

## Settings

All optional, set as environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `BUDGET_BUDDY_DATA_DIR` | `%LOCALAPPDATA%\BudgetBuddy` (Windows), `~/.local/share/budget-buddy` (others) | Where your data is kept. Never inside this repo. |
| `BUDGET_BUDDY_HOST` | `127.0.0.1` | Network address to listen on. The default means "this computer only". |
| `BUDGET_BUDDY_PORT` | `8765` | Port to listen on. |
| `BUDGET_BUDDY_DEV_MODE` | `false` | Set to `true` to turn on the API explorer at `/docs` (for developers). |
| `BUDGET_BUDDY_KEY_STORE` | `keyring` | Where the encryption key is kept. Leave this alone: `memory` is for developers' automated tests only (see below). |

On macOS/Linux the data folder is made readable only by your user account.

**Developers only:** automated tests and CI have no password vault, so they keep the key in
memory with `BUDGET_BUDDY_KEY_STORE=memory` **plus** `BUDGET_BUDDY_INSECURE_TEST_KEYSTORE=1`.
The key is lost when the process stops, so this only works on a new, empty data folder and is
refused on any folder that already has data or a `key-fingerprint` file. `tests/conftest.py`
and the CI workflow set both. Never use it for real data.

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
