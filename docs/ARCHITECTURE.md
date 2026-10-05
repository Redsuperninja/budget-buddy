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
- Includes a small local web dashboard (served by the same app) for the computer side:
  importing bank CSVs, entering paychecks, reviewing tax items, and showing the pairing QR code.
- Modules:
  - `accounts` — checking & savings accounts, balances
  - `transactions` — imported/entered transactions, categories, auto-categorization rules
  - `paychecks` — gross, withholdings, deductions, net
  - `receipts` — photo storage (encrypted), amount, merchant, category, optional OCR
  - `budget` — suggestions + monthly targets vs. actual
  - `tax` — charitable donations, stock lots/sales (cost basis, short/long-term), other deductions, yearly summary
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
| `donations` | id, date, organization, amount_cents (≥ 0), kind (cash/goods), receipt_id? |
| `stock_lots` / `stock_sales` | lot: symbol, shares_micro (millionths of a share, > 0), acquired_on, cost_basis_cents (≥ 0) · sale: lot_id, sold_on, shares_micro (> 0), proceeds_cents (≥ 0) → gain and term are calculated, not stored |
| `deductions` | id, tax_year (2000–2100), kind (medical/education/student_loan_interest/home_office/mortgage_interest/property_tax/state_local_tax/hsa/ira/childcare/other), description, date?, amount_cents (≥ 0), receipt_id? |
| `devices` | id, name, token_hash, sync_key (enc, deleted on revoke), nonce_watermark, revoked, paired_at, last_sync_at |
| `pairing_sessions` | id, code_hash, pair_pub, pair_sk (deleted when the session ends), exp, used_at, wrong_code_count |
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
`budget.db.bak-<revision>` is saved next to it.
