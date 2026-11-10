# Changelog

One line per change, newest first. Add yours under **Unreleased**; it moves into a version when we release.
The day-by-day list from before 0.1.0 is in this file's git history (`git log -p CHANGELOG.md`).

## Unreleased

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
