# Data model

Models live in `server/app/models/` (`ledger.py`, `tax.py`, `devices.py`). `(enc)` marks an encrypted column
([security.md](security.md)); `?` marks an optional one.

| Table | Key fields |
| --- | --- |
| `accounts` | id, name, kind (checking/savings/brokerage/credit_card/cash/loan/retirement/hsa/other), retirement_type? (roth_ira/traditional_ira/401k/roth_401k/403b/other; retirement accounts only), institution, last4 (enc), notes (enc) |
| `transactions` | id, account_id, date, amount_cents (signed: negative = money out), description, category_id, source (csv/manual/receipt), kind (normal/transfer/refund/adjustment), transfer_pair_id? (the other side of a transfer), notes (enc), import_fingerprint? (CSV import, unique), category_source? (rule/you), sorted_by_rule_id? |
| `csv_import_mappings` | account_id (PK, deleted with the account), mapping (JSON: which column is what, date format, sign flip) |
| `categories` | id, name, group (needs/wants/savings/income/transfer), budget_cents, budget_percent_bp? (share of income, 1 to 10,000) |
| `budget_plan` | id (always 1), planned_income_cents? (what percentage budgets are shares of) |
| `category_rules` | id, pattern (unique, "description contains"), category_id (deleted with its category) |
| `paychecks` | id, pay_date, employer, account_id?, deposit_transaction_id? (unique), gross_cents, federal_tax_cents, state_tax_cents, social_security_cents, medicare_cents, retirement_cents, hsa_cents, health_insurance_cents, roth_retirement_cents, other_deductions_cents, net_cents (all ≥ 0), notes (enc) |
| `receipts` | id, date, merchant, total_cents, category_id, image_path (enc), transaction_id?, tax_deductible flag, notes (enc), client_id? (unique), deduction_kind?, device_id? (phone uploads) |
| `positions` | one line of a broker's positions file: account_id (cascade), symbol (unique per account), shares_micro (> 0), cost_basis_cents?, value_cents?, as_of |
| `imports` | one imported file: kind (bank/stocks/activity/positions), account_id?, file_name (enc), rows_added; rows it added carry `import_id` |
| `dividends` | id, transaction_id (unique; the dividend payment), sweep_transaction_id? (unique; its deposit sweep), payer, dismissed |
| `donations` | id, date, organization, amount_cents (> 0; for goods, fair market value), kind (cash/goods), receipt_id?, transaction_id? (unique; the payment it came from), notes (enc) |
| `stock_lots` | one purchase: account_id?, symbol, shares_micro (millionths of a share, > 0), acquired_on, cost_basis_cents (≥ 0, fees included), transaction_id? (unique; the payment it was classified from) |
| `stock_sale_orders` | one sale as entered: account_id?, symbol, sold_on, shares_micro (> 0), proceeds_cents (≥ 0, after fees), transaction_id? (unique; the deposit it was classified from) |
| `stock_prices` | symbol (primary key), price_cents per share (≥ 0), as_of, source (you/feed), fetched_at?: the latest price |
| `price_feed` | id (1), enabled, api_key (enc): live prices from Finnhub (ADR-0010) |
| `stock_sales` | one lot's part of an order: order_id (cascade delete), lot_id, sold_on, shares_micro (> 0), proceeds_cents (≥ 0); rebuilt with FIFO ([stocks.md](stocks.md)) |
| `deductions` | id, tax_year (2000–2100), kind (medical/education/student_loan_interest/home_office/mortgage_interest/property_tax/state_local_tax/hsa/ira/childcare/other), description? (enc), date?, amount_cents (≥ 0), receipt_id? |
| `devices` | id, name, token_hash, sync_key (enc, deleted on revoke), platform, app_version, nonce_watermark, revoked, revoked_at, paired_at, last_sync_at |
| `pairing_sessions` | id, code_hash, pair_pub, pair_sk (enc, erased when the session ends), created_at, exp, used_at, cancelled_at, wrong_attempts |
| `pairing_nonces` | session_id, nonce (bytes); UNIQUE(session_id, nonce); replay cache for `/api/pair`, removed with the session |
| `seen_nonces` | device_id, nonce (bytes), ts; UNIQUE(device_id, nonce); replay cache pruned below the device's watermark |

- **Money is always integer cents**, never floats. Share quantities are integer millionths (`shares_micro`).
- Stock cost, gain, term and wash-sale flags are calculated, not stored.
- Every table also has `created_at` / `updated_at`.
- Changing a table means a new migration ([database.md](database.md)).
