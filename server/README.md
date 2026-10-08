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

Then open <http://127.0.0.1:8765/> in your browser: that is the Budget Buddy dashboard. (To check the server
alone, <http://127.0.0.1:8765/api/health> should show `{"status": "ok", ...}`.)

## The dashboard

The web page lives in its own top-level folder, [`dashboard/`](../dashboard/README.md), and is not part of the
server's code. The server finds the folder at startup (default `<repo>/dashboard`, or
`BUDGET_BUDDY_DASHBOARD_DIR`) and serves `GET /` and `GET /static/{path}` from an allowlist: `index.html`, top-level
`*.css` and `js/**/*.js` only, no symlinks, nothing outside the folder, size-capped. If the folder is missing, the
server runs **API only**: `/` shows a plain 404 page and every `/api/...` route works. A non-editable
`pip install` doesn't include `dashboard/`, so it serves the API only until the installer (roadmap #22) ships it.

Pages answer this computer only. Responses carry a strict Content-Security-Policy, `nosniff`, `no-referrer`, and the
HTML is `no-store`. Writes need a matching `Origin` and the per-run token in `X-CSRF-Token`: the page gets the token
in `<meta name="csrf-token">`; scripts can read it from `GET /api/local/csrf-token` (this computer only). Missing
or wrong token gives 403 `bad_origin`. The QR code comes from the `segno` package, a normal dependency.
Server tests use a fake dashboard folder (`fake_dashboard` in `tests/conftest.py`), never the real one.

## Try it with demo data

The `scripts\` folder at the top of the repo starts a separate **test** Home Base (its own data folder,
port 8766) and fills it with made-up data. See [docs/TESTING.md](../docs/TESTING.md). `scripts\setup.ps1`
installs everything they need.

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
phone's routes: `/api/health`, `/api/pair`, and later `/api/sync/*`. Requests must also be
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
- Categories: `GET/POST /api/local/categories` and `GET/PATCH /api/local/categories/{id}`. You can add a
  category, rename it, and set its monthly `budget_cents` (not negative; it applies to every month). The
  group can't be changed, and you can't add a `transfer` one. Names can't repeat, ignoring case.
- Monthly summary: `GET /api/local/summary/monthly?month=2026-01` gives income, spending, and savings for
  that month. Transfers and adjustments aren't counted, refunds lower spending, and transactions without
  a usable category are reported as `unassigned_in_cents` / `unassigned_out_cents` instead of being
  guessed at. Money moved to your own savings account isn't counted as saved yet.
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
- Paychecks: `GET/POST /api/local/paychecks` (filter: `year`), `GET/PATCH/DELETE
  /api/local/paychecks/{id}`, `POST/DELETE /api/local/paychecks/{id}/deposit` to link or unlink the
  bank deposit, and `GET /api/local/paychecks/summary?year=2026` for year-to-date totals. Amounts
  are whole cents only. See [docs/paychecks.md](../docs/paychecks.md).
- Receipts: `GET/POST /api/local/receipts` (`limit`, `offset`; newest first) and
  `GET/PATCH/DELETE /api/local/receipts/{id}`. A receipt has a `date`, `merchant` (the shop),
  `total_cents` (zero or more), and optionally a `category_id`, a `transaction_id` (the matching
  bank transaction), `tax_deductible`, and `notes` (encrypted). `has_image` says whether a photo is
  attached. Deleting a linked transaction or category just unlinks the receipt.

### Receipt photos

- **Add or replace:** `PUT /api/local/receipts/{id}/image` with the photo's bytes as the request
  body (not a form upload). JPEG, PNG or HEIC, up to **3 MB**. The type is worked out from the
  file's first bytes, so a renamed file or a wrong `Content-Type` doesn't fool it. Too big gets
  413 `image_too_large`; anything that isn't a readable photo gets 422 `image_invalid`.
- **See it:** `GET /api/local/receipts/{id}/image` shows it in the browser; add `?download=true`
  to save it instead. It's named `receipt-<id>.<jpg|png|heic>`, never after the shop.
- **Remove it:** `DELETE /api/local/receipts/{id}/image` (the receipt details stay).

What happens to a photo:

- **Hidden details are removed first.** Phones and cameras tuck extra information into photos,
  such as where the picture was taken and which phone took it. For JPEG and PNG, Budget Buddy
  keeps only the picture (and its colour profile) and throws the rest away before saving. Side
  effect: a photo taken sideways may show sideways, because the "rotate me" note goes too.
- **HEIC photos are saved as they are**, so they may still hold the photo's location. It's
  encrypted and never leaves your computer, but if that bothers you, save the photo as JPEG
  first. Fixing this is tracked in [issue #34](https://github.com/Redsuperninja/budget-buddy/issues/34).
- **It's encrypted** before it's written to `receipts/` in the data folder, under a random file
  name with no shop, date or amount in it. The plain photo is never written to disk.
- **Deleting a receipt deletes its photo file.** If Budget Buddy is stopped part-way through
  (say a power cut), the worst case is an unused encrypted file. Those are removed the next time
  Budget Buddy starts, once they're over an hour old. Files Budget Buddy didn't make are never
  touched.
- Reading text off the photo (OCR) isn't built yet: see
  [issue #33](https://github.com/Redsuperninja/budget-buddy/issues/33).
- Donations: `GET/POST /api/local/donations` (filters: `tax_year`, `kind`, `limit`, `offset`;
  newest first) and `GET/PATCH/DELETE /api/local/donations/{id}`. Each gift has a date, the
  charity's name (`organization`), a kind (`cash` or `goods`), an amount (`amount_cents`, or
  `amount` as dollar text; for goods, what the items were worth), and optionally a `receipt_id`
  and notes. The amount must be more than zero, and the date can't be more than one day in the
  future. `GET /api/local/donations/summary/{tax_year}` gives that year's cash, goods and overall
  totals and the proof to keep for each gift, using the thresholds in that year's tax data file.
  It's an estimate, not tax advice, and the totals are what you gave, not what you can deduct.
  See `docs/guide/donations.md`.

## Pairing a phone

Pairing connects one phone to this computer, once. On the computer you ask for a one-time code,
and the phone scans it as a QR code (or you paste it as text). The code works once and runs out
after 10 minutes. The QR holds no secret key, so a photo of it isn't enough to read anything.
Paired phones are listed, and you can remove one at any time; it stops working right away.

These routes answer this computer only (the phone uses `POST /api/pair`):

- `POST /api/local/pairing`: starts pairing and returns the QR contents (`payload`), the same
  contents as one line of text (`payload_text`, for "Show code as text"), when it runs out
  (`expires_at`), and `phone_can_connect` with a plain-English `message` if a phone can't reach
  this computer yet. It also has `qr_svg`, the QR code as an SVG picture for the dashboard. Starting
  again cancels the earlier code. Never share or save the result.
- `GET /api/local/devices`: connected phones (name, platform, app version, when paired, last sync,
  removed or not). Never shows codes or keys.
- `POST /api/local/devices/{id}/revoke`: removes a phone.
- `POST /api/pair` (phone, home network): the encrypted pairing request. Errors use the codes in
  `docs/api/sync-contract.md`.

### Phone sync endpoints (roadmap #15)

These answer the home network (and this computer). Each needs `Authorization: Bearer <device token>`
and a JSON body in the encrypted envelope of `docs/api/sync-contract.md` section 4. Replies are
encrypted too, including errors once the message has been opened; before that, errors are plain
`{"error": {"code", "message"}}` (for example `not_paired`, `device_revoked`, `clock_skew`,
`decrypt_failed`, `too_large`). A request can only be used once, and a removed phone is refused at once.

- `POST /api/sync/snapshot` (body up to 16 KiB): this month's budget by group and category (plus money
  not yet in a category), the last 60 days of transactions (at most 500), every account's balance up to
  today, income received and expected, and tax totals. No account numbers,
  notes, receipt photos, or employer names.
- `POST /api/sync/receipts` (body up to 12 MiB): 1 to 5 receipts, each with a JPEG photo
  (up to 3 MiB, 4096 pixels a side, 16 megapixels). The answer has one result per receipt:
  `accepted`, `duplicate` (this phone already sent that `client_id`; nothing new is stored; another phone's ID is `rejected`) or `rejected`
  with a reason. Photos are stored encrypted, like receipts added on the computer.
- `POST /api/sync/ack` (body up to 16 KiB): the phone finished a sync; sets the phone's "last synced".

The database gets a `seen_nonces` table, `devices.nonce_watermark`, and `receipts.client_id` /
`receipts.deduction_kind` / `receipts.device_id` (migration 0008); the app upgrades itself on start.
- Stocks (estimates, not tax advice; plain-English guide in
  [docs/guide/stocks.md](../docs/guide/stocks.md)):
  - `GET/POST /api/local/stocks/lots` and `GET/DELETE /api/local/stocks/lots/{id}`: shares you
    bought. Send the symbol, `acquired_on`, the shares as text (`"shares": "2.5"`) or in millionths
    (`shares_micro`), and the total you paid including fees (`cost_basis` dollar text or
    `cost_basis_cents`). Each purchase shows how many shares are left and the first date a sale of
    them counts as long term. Filters: `symbol`, `account_id`.
  - `GET/POST /api/local/stocks/sales` and `GET/DELETE /api/local/stocks/sales/{id}`: shares you
    sold, with the total you received after fees (`proceeds` or `proceeds_cents`). Each sale lists
    which purchases it used (oldest first), with cost, gain or loss, short or long term, and a
    possible-wash-sale flag. Filters: `symbol`, `account_id`, `tax_year`. Newest first.
  - `GET /api/local/stocks/gains/{tax_year}`: short- and long-term totals for sales in that year.
  - Selling more shares than you held is refused (`not_enough_shares`), and so is deleting a
    purchase a sale still needs (`purchase_in_use`). There's no editing: delete and enter again.
    Retirement and HSA accounts can't be used, and an account with stock records can't be
    deleted or changed into one.

## Settings

All optional, set as environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `BUDGET_BUDDY_DATA_DIR` | `%LOCALAPPDATA%\BudgetBuddy` (Windows), `~/.local/share/budget-buddy` (others) | Where your data is kept. Never inside this repo. |
| `BUDGET_BUDDY_HOST` | `127.0.0.1` | Leave unset. Budget Buddy listens on this computer only and opens a home-network connection by itself while pairing or once a phone is paired. Set to `127.0.0.1` to never allow phones. Setting any other address makes that the main listener (not recommended). |
| `BUDGET_BUDDY_LAN_IP` | detected | This computer's home-network address (such as `192.168.1.20`), put in the pairing QR and used for the phone connection. Set it if detection picks the wrong one. Must be a private address. |
| `BUDGET_BUDDY_SERVER_NAME` | `Home Base` | The name your phone shows for this computer (50 characters at most). |
| `BUDGET_BUDDY_PORT` | `8765` | Port to listen on. |
| `BUDGET_BUDDY_DASHBOARD_DIR` | `<repo>/dashboard` | Folder with the web dashboard files. If it isn't there, the server runs API-only (no web page). |
| `BUDGET_BUDDY_DEV_MODE` | `false` | Set to `true` to turn on the API explorer at `/docs` (for developers). |
| `BUDGET_BUDDY_KEY_STORE` | `keyring` | Where the encryption key is kept. Leave this alone: `memory` is for developers' automated tests only (see below). |

On macOS/Linux the data folder is made readable only by your user account.

### Moving your data folder

If the Home Base warns that your data folder is inside a code project or a cloud-synced folder
(OneDrive, Dropbox, iCloud, Google Drive, Box, pCloud, Nextcloud), move it:

1. Close the Home Base.
2. Move the whole data folder to a place that isn't synced, for example
   `C:\BudgetBuddyData` on Windows or a folder in your home folder on macOS/Linux.
3. Set `BUDGET_BUDDY_DATA_DIR` to the new folder's full path, then start the Home Base again.

Your encryption key stays in this computer's password vault, so it still works after the move.
On a Mac, `Desktop` and `Documents` are synced by iCloud when "Desktop & Documents Folders" is
turned on, so Budget Buddy warns about those too.

**Developers only:** automated tests and CI have no password vault, so they keep the key in
memory with `BUDGET_BUDDY_KEY_STORE=memory` **plus** `BUDGET_BUDDY_INSECURE_TEST_KEYSTORE=1`.
The key is lost when the process stops, so this only works on a new, empty data folder and is
refused on any folder that already has data or a `key-fingerprint` file. `tests/conftest.py`
and the CI workflow set both. Never use it for real data.

## Letting your phone connect

Nothing to set up. The Home Base normally listens to this computer only. While you're pairing a
phone (after you click **Pair a phone**), and from then on while at least one phone is paired, it
also opens a second connection on this computer's own home-network address (for example
`192.168.1.20`), never on every network. When no pairing is in progress and no phone is paired,
that connection is closed again. If Budget Buddy can't work out your address, set
`BUDGET_BUDDY_LAN_IP`.

The first time, Windows Firewall will ask whether to allow Python on networks. Tick
**Private networks** only. Leave **Public networks** unticked, so the Home Base stays hidden on
coffee-shop or airport Wi-Fi.

If you set `BUDGET_BUDDY_HOST` yourself, that choice wins: `127.0.0.1` means phones can never
connect (pairing will tell you so), and any other address is used as the main listener.

Even then, the server only answers requests from this computer or your home network; anything
else gets "403 Forbidden".
