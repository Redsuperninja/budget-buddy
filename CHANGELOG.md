# Changelog

One line per change, newest first. Add yours under **Unreleased**; it moves into a version when we release.
The day-by-day list from before 0.1.0 is in this file's git history (`git log -p CHANGELOG.md`).

## Unreleased
- For developers (roadmap 26-2, bank-file import): `POST /api/local/accounts/{id}/ofx-import/preview` and `.../ofx-import` read a bank or card OFX/QFX file the way the CSV import does. The bank's transaction ID (`FITID`) is the duplicate check, so importing the same or an overlapping file adds nothing. The file's last four account digits must match the account's (the first import asks to confirm and saves them), a file with several accounts needs one chosen, and it shows up in import history. A card file that lists charges as positive numbers is held back with a plain warning until you choose to flip it (`flip_sign`), so purchases can't import as money in by accident. The preview also lists new rows that look like something already in the account (same date and amount), keeps problem notes and row numbers per account, quietly skips $0.00 lines, and says a changed amount may be your own edit. The upload check is now shared with the CSV import. Sending `flip_sign=true` for a non-card account is refused, a re-import of a flipped file says the signs differ instead of "edited", and the 26-5 guide must mention year-end dates (the bank's stated date is kept). No page uses the routes yet (26-5). See [ADR-0016](docs/adr/0016-ofx-import.md).
- For developers (issue #13, paychecks): two more paycheck line kinds, `qualified_tips` and `qualified_overtime` (migration 0033), for the pay behind the 2025-2028 tips and overtime deductions. They are already part of gross pay, so they never change take-home or the adds-up check, and they stay taxed for Social Security, Medicare and federal withholding. The paycheck year summary has `line_totals` for them and the tax summary's Pay section lists each one when it isn't zero. No deduction amount or limit is worked out. The dashboard can't enter paycheck lines yet.
- Transactions page (roadmap 10f-5): a **Split** button on a payment or refund opens an editor to put it in 2 to 20 categories, with a running "left to assign" that must reach $0.00 before you can save, a note per part, and **Undo split**. A split transaction shows "Split (3 parts)" in the category column, with the parts on hover, instead of "No category".
- For developers (roadmap 10f-4, loan payments): a split whose one Transfer-group part equals a loan account's deposit can be linked to it through the manual transfer link (`services/ledger/split_loans.py`). The loan side becomes a transfer, the split stays regular so its interest or escrow parts still count as spending, and the principal isn't counted as saved. While linked, the split can't be changed, undone or deleted (409 `part_of_transfer`); unlinking frees it. Matching still never links a split. See [ADR-0017](docs/adr/0017-transaction-splits.md).
- For developers (roadmap 10f-3, transaction splits): nothing outside the split route touches a split transaction. A new `splits()` role in `transaction_roles.py` keeps it out of auto-sort rules, the "no category yet" filter, transfer, card-payment, dividend and bank-trade matching, repeat gifts and the pay-deposit list; linking it to a transfer, paycheck, donation, personal gift or stock trade is a 409 `split_transaction` (`refuse_if_split`).
- For developers (roadmap 10f-2, transaction splits): new `services/budget/category_lines.py` gives one line per unsplit transaction and per split part. The monthly summary, spending pace and the Transactions category filter read it, so a split transaction counts once per part, each in its own category, and the grand total is unchanged. With no splits every number is the same as before. See [ADR-0017](docs/adr/0017-transaction-splits.md).
- For developers (roadmap 10f-1, transaction splits): new `transaction_splits` table (migration 0032, encrypted note), `services/ledger/splits.py` and `PUT /api/local/transactions/{id}/splits` store a transaction's parts (2 to 20, same sign, adding up exactly) and show them as `splits` on every transaction. A split's category and amount can't be changed until the split is undone (409 `split_transaction`), and a category a part uses can't be deleted. Budget totals don't read the parts yet (10f-2). See [ADR-0017](docs/adr/0017-transaction-splits.md).
- For developers (roadmap 26-1, bank-file import): `services/imports/ofx_parsing.py` reads a bank's OFX/QFX download (the SGML and XML kinds): the bank's own transaction IDs, exact cents, dates, the statement balance and the last four digits of the account. It's our own small tag reader, so nothing in the file is expanded or followed. No page or route uses it yet (26-2 adds them). See [ADR-0016](docs/adr/0016-ofx-import.md).

## 0.1.0 (first public version)
What Budget Buddy does, in plain English. The roadmap numbers are in [docs/ROADMAP.md](docs/ROADMAP.md).

**Your money**
- Accounts and transactions: add, edit, search, and sort them by hand or with auto-sort rules that learn. Transfers
  between your own accounts are found for you, credit cards and loans show what you owe, and you can match your
  bank's balance.
- Import bank CSV files, a broker's activity file and a broker's positions file. Dividends, stock trades, paychecks
  and deposit sweeps are recognised, with a list of sweeps that still need checking.
- Paychecks with every pay-stub line, and stocks with purchases, sales, gains and optional live prices (your own
  free Finnhub key).

**Budgets and taxes**
- Monthly budgets by category (dollars or a share of income), a suggested 50/30/20 plan, spending pace and
  over-budget warnings.
- Tax summary: donations (cash and goods), stock gains, other deductions and a filing-status choice. US federal
  taxes only. Tax-year numbers for 2025 and 2026 come with sources, and results are estimates, not advice.

**The dashboard**
- Runs on your own computer: a simple view for everyday use with every tool one switch away, light and dark
  looks, charts on Home, a Get started checklist, a Setup page for the first start, and About with the privacy
  statement and licences. It also opens in a phone's web browser at home.
- Windows download with an installer, a desktop app (own window and tray icon, can start with Windows) and a
  start script that also works on Mac and Linux.

**Your phone**
- A paired phone app downloads an encrypted budget summary, keeps it encrypted on the phone, takes receipt
  photos (location and camera details are removed), queues them offline and reminds you to sync.

**Privacy and safety**
- Your whole database is encrypted (SQLCipher) with a key kept in your computer's password vault, plus extra
  encryption for the most private fields. Encrypted backups can be made and restored in the dashboard or with
  `python -m app backup`, and your recovery phrase can be shown. Nothing leaves your computer except the
  optional price feed.
- Public-repo guard (no real data or personal details can be committed), licences in the download, a privacy
  statement and a security policy.

**For developers and testers**
- Server in areas (ledger, imports, budget, investing, tax, devices); dashboard in one folder per section; shared
  CSV header search and one clock; checks that the dashboard, phone and server agree on every route.
- Scripts are Python with thin launchers (ADR-0011); `check_all.py`, `check_pages.py` and `tidy_branches.py`
  replace the PowerShell versions; lock files with hashes; faster server tests and a faster, smaller app.
- Specialized AI agents (`.claude/agents/`, `docs/dev/workflow.md`) with required reviewers; GitHub CI is
  paused until 2026-11-22 and runs by hand.
- Testing kit with made-up data in `scripts/testing/` and `docs/testing/`.
