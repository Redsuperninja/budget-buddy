# Roadmap

Each line is planned as **one small pull request**. Owner = the specialized agent that leads it
(see [dev/workflow.md](dev/workflow.md)).

## What's next (milestones)

Numbers are roadmap items below; `#N` are GitHub issues. Work top to bottom. D (easy start) is done; the first
Windows release (G) is being prepared alongside what's left of B (2026-10-09).

**A. Tester preview** (now): people can try the Home Base with demo data and connect a phone.
- [x] User-testing kit: setup and start scripts, demo data, pairing QR, CSV import helper, [testing guide](testing/set-up-for-testing.md).

**B. Alpha: the whole loop works for a non-technical tester.** The biggest gap today is that the
computer has no friendly screen and the phone only shows sample data.
1. ~~**16. Local web dashboard.**~~ Comes first, because it's how testers will use the computer. Must include the
   CSRF/DNS-rebinding protection (#4), showing the pairing QR, CSV upload, and polling the device list.
2. **15. Encrypted sync** (snapshot download, receipt upload), with the phone-side checks: #19 (encrypt the
   cached snapshot), #20 (size limits), #23 and #24 (stale or inconsistent snapshots).
3. **21. Sync button + reminders**, then **20. Receipt capture** with the offline queue.
4. Quick fixes from testing so far: validation messages that show internal names (for example
   `<TransactionKind.NORMAL: 'normal'>`), "1 rows" wording in CSV import errors, #31 (accept `.50` and `12.`),
   #29 (future-dated transactions in balances), #25 and #32 (show negative balances as money owed).

**C. Tax-season beta: the numbers people file with.** Items 1 to 3 done (PRs #59 to #63).
1. ~~**10. Budget engine** and **10b** (count transfers into savings as saved).~~
2. ~~**9. Auto-categorization rules.**~~
3. ~~**13. Other deductions + yearly tax summary export.**~~ (PDF through the browser's print dialog)
4. Follow-ups: #13 (paycheck detail lines), #14 (stock acquisition kinds and basis adjustments),
   #15 (donation detail fields), #30 (loan principal vs. interest), #33 (receipt OCR), #34 (HEIC metadata).

**D. Easy start (done).** Starting Budget Buddy should be a double-click, not three PowerShell windows.
1. ~~**22a. One start script:**~~ sets itself up on first run, starts the Home Base, opens the dashboard, and stops
   cleanly; replaces the separate setup and start steps for everyday use.
2. ~~**22. Desktop app ([ADR-0008](adr/0008-desktop-app.md)):**~~ `Budget Buddy.exe` with its own window
   showing the dashboard, no Python install needed; Start menu and desktop shortcut.
3. ~~**22b. Light start at login:**~~ an optional tray icon that starts with Windows and only fully starts Budget
   Buddy when you open it.

**E. Bank data, free and open source first ([ADR-0006](adr/0006-bank-connections.md)).** Checking, savings and
investment data from banks like Chase and Wells Fargo without hand-mapping CSV files.
1. **26. Bank-file import (OFX/QFX):** balances, the bank's own transaction IDs, brokerage holdings.
2. **27. Auto-import folder:** new bank files in a chosen folder (like Downloads) are imported automatically.
3. **28. Optional live connection, bring your own free developer key** (Teller first, Plaid if needed); test
   with the owner's own banks before building.

**F. Fuller phone app ([ADR-0007](adr/0007-standalone-phone-app.md), accepted).** After milestone B's phone
items (20, 21).
1. **29. Phone database** (encrypted on-device SQLite) and shared budget-math test vectors.
2. **30. Sync contract v2:** two-way changes with conflict rules.
3. **31. Edit on the phone:** transactions, categories, budgets, suggested budget.
4. **32. Standalone mode:** use the phone with no Home Base; pair one later.

**G. Public release.**
1. **24. Encrypted backup & restore**, **23. User guide with screenshots**.
2. Security hardening: #6 (supply chain: lock file, pinned actions, Dependabot), #26, #27 and #28 (key and
   encryption hardening), #21 (npm advisories).
3. **25. Public release prep.**

## Phase 1: Foundation
- [x] 1. Repo scaffold, docs, agent definitions — *architect*
- [x] 2. Home Base skeleton: FastAPI app, config, data folder, health check, tests, CI — *backend-engineer*
- [x] 3. Database layer: SQLAlchemy models + Alembic migrations, money-in-cents helpers — *backend-engineer*
- [x] 4. Encryption at rest: keyring master key, encrypted file storage — *backend-engineer* + *security-reviewer*

## Phase 2: Getting data in
- [x] 5. Accounts + transactions API (manual entry) — *backend-engineer*
- [x] 5b. Categories API (list, add, rename, monthly budget) + monthly income/spending summary — *backend-engineer* + *finance-tax-expert*
  - Adjustments (including opening balances) change balances but are never counted as income or spending.
    Transfers are excluded too (see "Transaction kinds" in [dev/architecture/ledger.md](dev/architecture/ledger.md)).
- [x] 5d. An "Other Expenses" category for spending that fits nowhere else — *backend-engineer*
- [x] 5c. Match an account's balance to the bank (today, start of year, or any day) with one adjustment — *backend-engineer* + *finance-tax-expert*
- [x] 6. Bank CSV import (checking/savings) with column mapping — *backend-engineer*
- [x] 6b. Import history: see every imported file and remove an outdated one (undo) — *backend-engineer* + *security-reviewer*
- [x] 7. Paychecks API — *backend-engineer* + *finance-tax-expert*
- [x] 7b. Pay deposits from bank files start a paycheck on the Paychecks page, linked to the deposit — *backend-engineer*
- [x] 8. Receipts API: encrypted photo upload, details, optional OCR — *backend-engineer*
- [x] 8b. Receipts page on the dashboard: photos, details, delete outdated ones — *backend-engineer*
  - OCR split out to issue #33; HEIC photos keep their metadata for now (issue #34).
- [x] 9. Auto-categorization rules — *backend-engineer* + *finance-tax-expert*
- [x] 9b. Auto-sort learns from your picks; see what was auto-sorted — *backend-engineer*
- [x] 9d. Hide balance adjustments on the Transactions page (on by default) — *backend-engineer*
- [x] 9c. Show only transactions with no category yet, to sort them quickly — *backend-engineer*

## Phase 3: Budget & taxes
- [x] 9b. Tax-year reference data (2025, 2026) — *finance-tax-expert*
- [x] 10. Budget engine: suggested budget (50/30/20 baseline from real data), targets vs actual — *finance-tax-expert*
- [x] 10d. Income has no budget: it's what the rest of the budget is measured against — *finance-tax-expert*
- [x] 10a. Budgets as a percentage of income (planned or actual), and each group's share of income — *finance-tax-expert*
- [x] 10b. Count transfers into your own savings accounts as saved (summary + budget engine) — *finance-tax-expert*
- [x] 10c. Match transfers between accounts automatically and say what kind they are — *backend-engineer* + *finance-tax-expert*
- [x] 11. Charitable donations tracking — *finance-tax-expert*
- [x] 11b. Sort a payment into charity: a donation linked to its transaction — *finance-tax-expert* + *backend-engineer*
- [x] 11c. Gift categories: charity gifts filed under "Charitable giving", personal gifts under "Gifts" — *finance-tax-expert*
- [x] 12. Stock lots & sales: cost basis, short/long-term gains — *finance-tax-expert*
- [x] 12c. Live stock prices from Finnhub, on demand and only when turned on (ADR-0010) — *backend-engineer* + *security-reviewer*
- [x] 12d. Import stock purchases and sales from a CSV file — *backend-engineer* + *finance-tax-expert* + *security-reviewer*
- [x] 12h. Delete a stock purchase or sale from the Stocks page, or undo one on the Transactions page — *backend-engineer*
- [x] 12g. Import a broker's positions file: a holdings snapshot per account, compared with your trades, prices updated — *backend-engineer* + *security-reviewer*
- [x] 12f. Record a stock purchase or sale from a transaction on the Transactions page — *backend-engineer* + *finance-tax-expert*
- [x] 12e. Dividends from your transactions: filed under Dividends, deposit sweeps linked, a yearly list, hide toggle — *backend-engineer* + *finance-tax-expert*
- [x] 12i. Retirement account types (Roth IRA, traditional IRA, 401(k)...), with Roth IRA money counted toward the IRA limit — *backend-engineer* + *finance-tax-expert*
- [x] 12b. Investments: stocks in any account, holdings and typed-in prices, retirement and HSA limits — *finance-tax-expert*
- [x] 13. Other deductions + yearly tax summary export (CSV/PDF) — *finance-tax-expert*

## Phase 4: Sync
- [x] 13b. Sync API contract v1 — *architect*
- [x] 14. Pairing: QR code, one-time code, device tokens, revoke — *backend-engineer* + *security-reviewer*
- [x] 15. Encrypted sync endpoints: snapshot download, receipt upload — *backend-engineer* + *security-reviewer*
- [x] 16. Local web dashboard (computer side) — *backend-engineer* (note: poll the device list while a QR is showing so the home-network listener closes after the code expires; no timer closes it)
- [x] 16b. Charts on the dashboard: spending against budget, the last 12 months — *backend-engineer*
- [x] 16e. Home redesign: money tiles, what needs you, where your income went, what you have and owe — *backend-engineer*
- [x] 16c. Tidier dashboard navigation: five sections with page tabs — *backend-engineer*
- [x] 16d. Use the dashboard from another computer at home, joined with a one-time code (ADR-0009) — *backend-engineer* + *security-reviewer*

## Phase 5: Phone app
- [x] 17. Expo scaffold, navigation, theme — *mobile-engineer*
- [x] 18. Pair screen (QR scan, secure key storage) — *mobile-engineer*
- [x] 19. Dashboard: budget breakdown from snapshot — *mobile-engineer*
- [ ] 20. Receipt capture with offline queue — *mobile-engineer*
- [ ] 21. Sync button + 1–3 day reminder notifications — *mobile-engineer*
  - Sync now button done (feat/phone-sync); reminders still to do

## Phase 6: Make it easy
- [x] 22a. One start script: first-run setup, start, open the dashboard, stop cleanly — *backend-engineer*
- [x] 22. Desktop app: `Budget Buddy.exe` with its own window (pywebview + PyInstaller), shortcuts — *backend-engineer* + *security-reviewer*
- [x] 22b. Light start at login: tray icon, full start on open, start-with-Windows setting — *backend-engineer* + *security-reviewer*
- [ ] 23. Plain-English user guide with screenshots — *docs-writer*
- [ ] 24. Encrypted backup & restore — *backend-engineer* + *security-reviewer*
- [ ] 25. Prep for public release: setup wizard, no personal defaults — *architect*
  - Done so far: Windows download with installer and uninstall (`scripts/release/make-release.ps1`, release workflow, [release.md](dev/release.md)); simple view with All tools; Get started checklist on Home; phone-friendly dashboard for a phone's browser

## Phase 7: Bank data (ADR-0006: free and open source first)
- [x] 26b. Brokerage activity CSV: every row a transaction, buys and sells linked as stock trades, dividends filed — *backend-engineer* + *finance-tax-expert*
- [ ] 26. Bank-file import (OFX/QFX): balances, bank transaction IDs, brokerage holdings — *backend-engineer* + *security-reviewer* + *finance-tax-expert*
- [ ] 27. Auto-import folder for new bank files — *backend-engineer* + *security-reviewer*
- [ ] 28. Optional live connection with your own free developer key (Teller, then Plaid) — *backend-engineer* + *security-reviewer*

## Phase 8: Fuller phone app (ADR-0007 accepted)
- [ ] 29. Encrypted phone database + shared budget-math test vectors — *mobile-engineer* + *security-reviewer* + *finance-tax-expert*
- [ ] 30. Sync contract v2: two-way changes, conflict rules — *architect* + *backend-engineer* + *mobile-engineer*
- [ ] 31. Edit on the phone: transactions, categories, budgets, suggested budget — *mobile-engineer*
- [ ] 32. Standalone mode (no Home Base needed; pair later) — *mobile-engineer* + *architect*
