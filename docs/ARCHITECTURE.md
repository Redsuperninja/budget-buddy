# Architecture

## Big picture

```
 ┌──────────────── Your home network ────────────────┐
 │                                                    │
 │  ┌──────────────┐   encrypted sync    ┌─────────┐  │
 │  │  Home Base   │ ◀────────────────▶ │  Phone   │  │
 │  │  (your PC)   │   (on home Wi-Fi)   │   app    │  │
 │  │              │                     └─────────┘  │
 │  │ FastAPI      │                                  │
 │  │ SQLite DB    │  ← data lives here only          │
 │  │ Receipt files│                                  │
 │  └──────────────┘                                  │
 └────────────────────────────────────────────────────┘
        Nothing is sent to the internet or a cloud.
```

### Home Base (`server/`)
- **Python + FastAPI** HTTP API, **SQLite** database, **SQLAlchemy** models, **Alembic** migrations.
- Data folder lives **outside the repo** (default `%LOCALAPPDATA%\BudgetBuddy` on Windows,
  `~/.local/share/budget-buddy` elsewhere). Code in git never contains personal data.
- Includes a small local web dashboard (served by the same app, `server/app/dashboard/`) for the computer side:
  accounts, transactions, categories, bank CSV import, paychecks, donations, stocks, and the pairing QR code.
  It is plain HTML, CSS and JavaScript with no build step and no internet requests (system fonts, local files
  only). It lives at `/` (assets at `/static/`) and answers this computer only, because it is not one of the phone
  routes. Every page response carries a strict Content-Security-Policy (`default-src 'self'`, no inline script,
  `frame-ancestors 'none'`), `nosniff`, `Referrer-Policy: no-referrer`, and the HTML is `no-store`. The page builds
  its screens with `textContent` only (never `innerHTML` with API data). Issue #4 (CSRF and DNS rebinding) is met
  by `LocalAccessMiddleware` plus that CSP: Host allowlist, loopback-only peer, `Origin` must match on every
  write, and a per-run CSRF token (random, in `app.state`, never logged) must come back in `X-CSRF-Token`
  (constant-time compare; failure is 403 `bad_origin`). The token is in a `<meta name="csrf-token">` tag of the
  page, and `GET /api/local/csrf-token` gives it to the helper scripts. There are no CORS headers, so other
  websites can't read it. The pairing QR is drawn on the server (`segno`) and returned as SVG; the QR still
  holds no secret key (ADR-0004).
- Modules:
  - `accounts` — checking & savings accounts, balances
  - `transactions` — imported/entered transactions, categories, auto-categorization rules
  - `paychecks` — gross, withholdings, deductions, net
  - `receipts` — photo storage (encrypted), amount, merchant, category, optional OCR
  - `budget` — suggestions + monthly targets vs. actual
  - `tax` — charitable donations, stock lots/sales (cost basis, short/long-term), other deductions, yearly summary
    - Donations (roadmap #11): `/api/local/donations` (this computer only) to add, list, edit, and
      remove cash and goods gifts, plus `GET /api/local/donations/summary/{tax_year}`. The summary
      totals what was given that calendar year and lists the proof each gift needs, and the
      paperwork that depends on the whole year (Form 8283, the "check similar items" note, and
      the 2026+ note for people who don't itemize). Every dollar threshold comes from that year's
      tax data file (`docs/tax-data.md`); a year without a file gets 404 `no_tax_data`. Totals are
      what was given, not what can be deducted, and every summary is labeled an estimate
      (`is_estimate`, `disclaimer`). Gift dates more than one day after the Home Base's date are
      rejected (pledges count once paid). User guide: `docs/guide/donations.md`.
  - `sync` — device pairing and the snapshot/upload protocol

### Phone app (`mobile/`)
- **Expo (React Native + TypeScript)**. Runs on iPhone and Android through Expo Go, no app store needed.
- Works **offline**: keeps the latest snapshot from the Home Base and a queue of receipt photos taken since.
- Screens: Pair (scan QR) · Dashboard (budget breakdown) · Add Receipt (camera) · Sync · Taxes summary.
- Local notification reminder when the last sync is older than the chosen interval (default 2 days, adjustable 1–3).

## Sync design (summary, see ADR-0002)

The exact wire format (QR payload, endpoints, encryption envelope, snapshot and receipt schemas, error
codes, reminder rules, test vectors) is in **[api/sync-contract.md](api/sync-contract.md)** (ADR-0004).

1. **Pairing (once):** the Home Base dashboard shows a QR code containing its LAN address,
   a one-time pairing code, and a short-lived **public** key. There's no secret in the QR. The phone sends its
   own fresh public key, both sides derive a shared key, and the Home Base answers, encrypted with it, with a
   device token and a new **sync key**. The phone keeps both in secure storage. The dashboard immediately shows
   "New phone paired" with a Remove button.
   Phone side (`mobile/src/sync/`, `mobile/src/app/pair.tsx`): the pair screen reads the QR (or pasted text),
   checks it (known version, the address is a private home-network IP, code not expired), sends one
   encrypted `POST /api/pair`, checks the answer is for that request and from the same computer, and only
   then saves the credentials, replacing any old ones. If the phone is already connected to a different
   computer, it asks first. Scanning is turned off on the web build.
   - *Server side (roadmap #14):* `POST /api/local/pairing` (this computer only) makes a session: a 16-byte
     one-time code (only its SHA-256 is stored), a fresh X25519 keypair (`pair_sk` stored encrypted and erased
     when the session ends), valid for 10 minutes, once. Starting a new one cancels the old one. The same call
     returns the QR payload as a JSON object and as one line of text ("Show code as text"). The phone calls
     `POST /api/pair`: encrypted and authenticated, replay-checked (nonces kept per session), limited to 10
     tries a minute per address, and 5 wrong codes end the session. Only a hash of the device token is kept; the
     sync key is stored encrypted.
   - *Devices:* `GET /api/local/devices` lists phones (never tokens or keys); `POST
     /api/local/devices/{id}/revoke` marks one removed and deletes its sync key, so its token stops working
     at once. The row stays as history.
   - *Home-network listener:* the main server listens on `127.0.0.1` only. While a pairing session is live, or
     while at least one phone is paired, `python -m app` also opens a second listener on this computer's own
     home-network address (`BUDGET_BUDDY_LAN_IP`, or detected), never `0.0.0.0`, and closes it when neither
     is true. It is re-checked when pairing starts, a phone is removed, and the device list is read (there is no
     timer: a listener for an expired, unused QR is closed at the next check; the dashboard polls the device list about every 3 seconds while a QR is showing). An explicit `BUDGET_BUDDY_HOST` wins:
     loopback means phones can never connect (pairing says so), another address is used as the main listener.
     The `Host` allowlist includes `{lan address}:{port}`.
2. **Sync (every 1–3 days):** on home Wi-Fi the user taps **Sync**. The phone:
   - uploads queued receipts (photo + details),
   - downloads a fresh **snapshot** (budget breakdown, recent transactions, tax summary).
3. All sync payloads are **encrypted end-to-end with the sync key** (NaCl secretbox), so even plain
   HTTP on the home network can't be snooped. Requests also need the device token.
4. Only health, pairing and sync endpoints answer the home network; the dashboard answers this computer only.
   Devices can be revoked from the dashboard.

Non-technical flow: *"Be home, open app, tap Sync."* If the phone can't reach the Home Base, it says so in plain
words ("Make sure your computer is on and Budget Buddy is running").

## Security at rest (see ADR-0003)
- Master key stored in the OS credential vault (Windows Credential Manager via `keyring`), never in files.
- Receipt images encrypted at rest (Fernet / AES).
- Sensitive DB fields (account numbers, notes) encrypted; whole-DB encryption evaluated as a follow-up.
- Encrypted backup export (single file) for the user to copy to a USB drive.

## Data model (initial)

| Table | Key fields |
| --- | --- |
| `accounts` | id, name, kind (checking/savings/brokerage/credit_card/cash/loan/retirement/hsa/other), institution, last4 (enc), notes (enc) |
| `transactions` | id, account_id, date, amount_cents (signed: negative = money out), description, category_id, source (csv/manual/receipt), kind (normal/transfer/refund/adjustment), transfer_pair_id? (the other side of a transfer), notes (enc), import_fingerprint? (CSV import, unique) |
| `csv_import_mappings` | account_id (PK, deleted with the account), mapping (JSON: which column is what, date format, sign flip) |
| `categories` | id, name, group (needs/wants/savings/income/transfer), budget_cents |
| `paychecks` | id, pay_date, employer, account_id?, deposit_transaction_id? (unique), gross_cents, federal_tax_cents, state_tax_cents, social_security_cents, medicare_cents, retirement_cents, hsa_cents, health_insurance_cents, roth_retirement_cents, other_deductions_cents, net_cents (all ≥ 0), notes (enc) |
| `receipts` | id, date, merchant, total_cents, category_id, image_path (enc), transaction_id?, tax_deductible flag |
| `donations` | id, date, organization, amount_cents (≥ 0; for goods, fair market value), kind (cash/goods), receipt_id?, notes (enc) |
| `stock_lots` / `stock_sales` | lot: symbol, shares_micro (millionths of a share, > 0), acquired_on, cost_basis_cents (≥ 0) · sale: lot_id, sold_on, shares_micro (> 0), proceeds_cents (≥ 0) → gain and term are calculated, not stored |
| `donations` | id, date, organization, amount_cents (≥ 0), kind (cash/goods), receipt_id? |
| `stock_lots` / `stock_sale_orders` / `stock_sales` | lot (a purchase): account_id?, symbol, shares_micro (millionths of a share, > 0), acquired_on, cost_basis_cents (≥ 0, fees included) · sale order (a sale as entered): account_id?, symbol, sold_on, shares_micro (> 0), proceeds_cents (≥ 0, after fees) · sale (one lot's part of an order): order_id, lot_id, sold_on, shares_micro (> 0), proceeds_cents (≥ 0), rebuilt with FIFO per symbol and account whenever a lot or order changes → cost, gain, term, and wash-sale flag are calculated, not stored (`app/services/stock_gains.py`) |
| `deductions` | id, tax_year (2000–2100), kind (medical/education/student_loan_interest/home_office/mortgage_interest/property_tax/state_local_tax/hsa/ira/childcare/other), description, date?, amount_cents (≥ 0), receipt_id? |
| `devices` | id, name, token_hash, sync_key (enc, deleted on revoke), platform, app_version, nonce_watermark (arrives with sync, #15), revoked, revoked_at, paired_at, last_sync_at |
| `pairing_sessions` | id, code_hash, pair_pub, pair_sk (enc, erased when the session ends), created_at, exp, used_at, cancelled_at, wrong_attempts |
| `pairing_nonces` | session_id, nonce (bytes); UNIQUE(session_id, nonce); replay cache for `/api/pair`, removed with the session |
| `seen_nonces` | device_id, nonce (bytes), ts; UNIQUE(device_id, nonce); replay cache pruned below the device's watermark |

Money is always stored as **integer cents**, never floats. Every table also has `created_at` / `updated_at`.

### Transaction kinds and what counts as income or spending

- `normal`: everyday money in or out. Counts as income or spending, decided by its category's group.
- `refund`: money coming back for an earlier purchase. **Always positive.** It nets against spending in
  its category; it is never income.
- `transfer`: one half of a linked pair moving money between two of your own accounts. Never income or
  spending.
- `adjustment`: corrects a balance, including the **opening balance** of a new account. **Adjustments
  (including opening balances) change balances but are never counted as income or spending.** They have
  no category, so they can't slip in through a category group.

### Signs and balances

`amount_cents` is signed from the account's point of view: **negative = money out, positive = money in**. An
account's balance is the plain sum of its transactions.

**For `credit_card` and `loan` accounts a negative balance means money owed. Charges are negative, and payments
and refunds are positive.** A card payment from checking is a linked transfer: -X on checking, +X on the card.
This makes net worth the plain sum of every account's balance. CSV import (#6) must flip card issuers that
export charges as positive numbers (the `flip_sign` choice, saved with the account's mapping). The dashboard should show a negative card balance as "$50.00 owed".

Worked example (fake data, also a test in `server/tests/test_accounts_api.py`):

| Account | Transaction | `amount_cents` |
| --- | --- | ---: |
| Checking | Opening balance (`adjustment`) | 200000 |
| Checking | Card payment (`transfer`, linked) | -30000 |
| Card | Charge | -12000 |
| Card | Charge | -25000 |
| Card | Refund | 2000 |
| Card | Card payment (`transfer`, linked) | 30000 |

Checking = **170000** ($1,700.00). Card = **-5000** ($50.00 owed). Sum of all balances = **165000**.

### Categories and the monthly summary

Routes (this computer only, like the rest of `/api/local/`): `GET/POST /api/local/categories`,
`GET/PATCH /api/local/categories/{id}`, and `GET /api/local/summary/monthly?month=YYYY-MM`.

- A category has a name (unique, ignoring upper/lower case), a group (`needs`, `wants`, `savings`,
  `income`, or the built-in `transfer`), and a `budget_cents` target. You can rename it and change its
  budget. The group can't change, and new categories can't use the `transfer` group.
- **Budgets apply to every month.** There is no per-month budget, so changing one also changes what past
  months show.
- The summary only counts `normal` and `refund` transactions, by their own date, from the first to the last
  day of the month. **Transfers and adjustments (including opening balances) are never counted.**
- The category's group decides where a transaction goes: `income` is income; `needs` and `wants` add up to
  `spending_cents`; `savings` is `saved_cents`. Spending and savings are shown as money out, positive.
  **Refunds lower spending** (or savings) in their category and are never income. Spending can go
  negative if refunds are bigger than spending.
- Transactions with no category, and refunds filed under an income or transfer category, can't be placed.
  They are not guessed at: they show up as `unassigned_in_cents`, `unassigned_out_cents` (both positive)
  and `unassigned_count`, and are left out of the totals.
- **Known gap:** money moved into your own savings account is a transfer, so it isn't counted as saved yet.
  Roadmap item 10b covers this.
### Paychecks and income (no double counting)

A paycheck records what you earned and what was taken out. The lines always add up exactly:
`gross - (federal + state + social_security + medicare) - (retirement + hsa + health_insurance)
- (roth_retirement + other_deductions) = net`, in whole cents, or the API answers 422
`net_mismatch` with the difference.

**Income in budget totals comes only from bank transactions. A paycheck is never counted as
income by itself.** Linking a paycheck to its deposit (`deposit_transaction_id`) only explains
that deposit, so the money is counted once: as the deposit. An unlinked paycheck adds nothing to
income either; its money shows up when the deposit is entered or imported. Paychecks feed the
tax side (wages and withholding by tax year, by `pay_date`) and the "expected take-home"
estimate, never "received".

Link rules: the deposit is a regular (`normal`) transaction of exactly `+net_cents` in a checking
or savings account, and one deposit backs at most one paycheck. While linked, the paycheck's net
and account and the deposit's amount, account and kind are locked (409), and the deposit can't
become half of a transfer. Deleting either side just removes the link.

### Database migrations

The schema is managed by Alembic (`server/app/migrations/`) and upgraded automatically when the Home Base starts,
under a lock file so only one copy migrates at a time. Before upgrading an existing database, a backup copy
`budget.db.bak-<revision>` is saved next to it. Migration 0004 adds the pairing tables and the new device columns above.
`budget.db.bak-<revision>` is saved next to it.

### Stocks: lots, sales, and gains (roadmap #12)

API: `/api/local/stocks/...` (this computer only), see `server/README.md`. User guide:
[guide/stocks.md](guide/stocks.md).

- **Tables.** `stock_lots` = one purchase. `stock_sale_orders` = one sale as the user entered it (symbol,
  date, shares, proceeds after fees, optional account). `stock_sales` = the part of an order that came out
  of one lot (`order_id`, `lot_id`, shares, that lot's share of the proceeds); deleting an order deletes
  its parts (`ON DELETE CASCADE`). Migration 0004 added `stock_sale_orders` and `stock_sales.order_id`.
- **Shares** are whole millionths of a share (`shares_micro`, `SHARES_SCALE = 1_000_000`), never floats.
  The API also takes and returns them as text (`"2.5"`).
- **FIFO, rebuilt.** Each symbol + account is matched on its own, oldest purchase first (same date: the
  one entered first), using only purchases dated on or before the sale. The `stock_sales` rows of that
  symbol + account are rebuilt on every add or delete, so a purchase entered late still sells first.
  A sale needing more shares than were held is refused (422 `not_enough_shares`); deleting a purchase
  a sale needs is refused (409 `purchase_in_use`). There's no edit: delete and re-enter.
- **Calculated, not stored** (`server/app/services/stock_gains.py`, no database code): cost basis per
  part, gain, term, wash-sale flag, and yearly totals.
  - Rounding: a lot's cost is shared out over its sold shares cumulatively, rounding half up, so a fully
    sold lot's parts add up to exactly its cost. A sale's proceeds are split over its lots the same way.
  - Term: the holding period starts the day after purchase. Long term = sold on or after the day one
    full year from that start has passed (`long_term_from`); a year starting Feb 29 ends Feb 28.
  - Possible wash sale (flag only, nothing adjusted): a loss part, with another purchase of the same
    symbol in any account entered here within 30 days before or after the sale. The rest of the losing
    lot doesn't count (Rev. Rul. 56-602); another lot the same sale used up completely doesn't count;
    one it only partly used does. IRA/HSA and spouse purchases aren't known, so they aren't checked.
  - Year: a sale counts in the year of its sale date (`GET /api/local/stocks/gains/{tax_year}`).
- **Statutory constants** (one year, 30 days) live in `stock_gains.py` with sources, not in the
  per-year tax data files: they don't change by year.
- **Accounts.** Retirement and HSA accounts can't hold tracked purchases or sales (sales there aren't
  taxed). An account with stock records can't be deleted or changed to one of those kinds.
- Every result is labeled an estimate, not tax advice.
