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

1. **Pairing (once):** the Home Base dashboard shows a QR code containing its LAN address,
   a one-time pairing code, and a fresh random **encryption key**. The phone scans it, stores the key in
   the phone's secure storage, and receives a device token.
2. **Sync (every 1–3 days):** on home Wi-Fi the user taps **Sync**. The phone:
   - uploads queued receipts (photo + details),
   - downloads a fresh **snapshot** (budget breakdown, recent transactions, tax summary).
3. All sync payloads are **encrypted end-to-end with the paired key** (NaCl secretbox), so even plain
   HTTP on the home network can't be snooped. Requests also need the device token.
4. The server only answers requests from private-network addresses. Devices can be revoked from the dashboard.

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
| `accounts` | id, name, kind (checking/savings/brokerage), institution, last4 (enc) |
| `transactions` | id, account_id, date, amount_cents, description, category_id, source (csv/manual/receipt) |
| `categories` | id, name, group (needs/wants/savings/income), budget_cents |
| `paychecks` | id, pay_date, employer, account_id?, gross_cents, federal_tax_cents, state_tax_cents, social_security_cents, medicare_cents, retirement_cents, hsa_cents, other_deductions_cents, net_cents |
| `receipts` | id, date, merchant, total_cents, category_id, image_path (enc), transaction_id?, tax_deductible flag |
| `donations` | id, date, organization, amount_cents, kind (cash/goods), receipt_id? |
| `stock_lots` / `stock_sales` | lot: symbol, shares_micro (millionths of a share), acquired_on, cost_basis_cents · sale: lot_id, sold_on, shares_micro, proceeds_cents → gain and term are calculated, not stored |
| `deductions` | id, tax_year, kind (medical, education, home office, HSA, etc.), amount_cents, receipt_id? |
| `devices` | id, name, token_hash, paired_at, last_sync_at, revoked |

Money is always stored as **integer cents**, never floats. Every table also has `created_at` / `updated_at`.
The schema is managed by Alembic (`server/migrations/`) and upgraded automatically when the Home Base starts.
