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
- Bank CSV import: `POST /api/local/accounts/{id}/csv-import/preview`, then
  `POST /api/local/accounts/{id}/csv-import`, and `DELETE /api/local/accounts/{id}/csv-import/mapping`
  to forget a saved mapping. See below.

## Importing a bank statement (CSV)

Most banks let you download your transactions as a CSV file ("Download" or "Export", then CSV).
Budget Buddy can read that file straight into one of your accounts.

1. **Preview.** Send the file to the preview route. The request body is the file itself
   (`Content-Type: text/csv`). Budget Buddy works out which column is the date, the description
   and the amount (or separate money-out and money-in columns), and shows you every row it would
   add. Nothing is saved yet.
2. **Check it.** Look at the dates and the signs. Money out should be negative. If something's
   off, send the preview again with your own choices as query parameters, for example
   `?date_format=DD/MM/YYYY` or `?flip_sign=true`. Columns are numbered from 0.
3. **Import.** Send the same file and the same choices to the import route. Add
   `save_mapping=true` and next time this account's file is recognized straight away.

Good to know:

- **Importing the same rows twice is safe.** Each imported row remembers a fingerprint (account,
  date, amount, description, and how many identical rows came before it in the file). If you
  import an overlapping statement, rows already in Budget Buddy are skipped and counted as
  `skipped_duplicates`. Two identical purchases on the same day in one file are both kept.
- **Credit cards:** many card companies list charges as positive numbers. Budget Buddy needs
  charges negative (money you owe), so choose `flip_sign=true` for those files.
- **Dates:** US-style month/day is tried first. If your bank writes day/month and every day in
  the file is 12 or less, choose `date_format=DD/MM/YYYY` yourself. Formats understood:
  `YYYY-MM-DD`, `MM/DD/YYYY`, `MM/DD/YY`, `DD/MM/YYYY`, `DD/MM/YY`, `YYYY/MM/DD`, `MM-DD-YYYY`,
  `DD.MM.YYYY`, `YYYYMMDD`, `Mon D, YYYY`, `D Mon YYYY` (a time after the date is ignored).
- **Amounts** may have `$` signs, thousands commas, `(12.34)` or `12.34-` for negatives. An
  amount that can't be read exactly, like `12,34` with a decimal comma, is never guessed: the row
  is reported as a problem.
- **Rows with problems** stop the import and are listed by row number, so nothing half-imports.
  Fix your choices, or add `skip_invalid_rows=true` to import the rest. Blank lines are ignored.
- **Limits:** 5 MB and 10,000 rows per file. Text files saved as UTF-8, UTF-16 or Windows-1252
  are all fine.
- A description that starts with `=`, `+`, `-` or `@` gets a `'` in front, so a spreadsheet never
  runs it as a formula if you export it later.
- Imported rows are regular transactions with no category. Transfers between your accounts
  aren't spotted automatically yet: link them yourself.

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
