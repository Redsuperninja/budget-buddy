# Tech debt and restructuring plan

A hand-off list (2026-10-09): what to clean up so Budget Buddy stays easy to change, and how to reorganize the
repository so a newcomer can find things. Each numbered item is sized as one small PR, in a sensible order. Nothing
here changes what the app does.

## 1. Before anything else

1. **Merge the open stack** bottom-first ([workflow.md](workflow.md#merging-a-stack-safely)). Twelve stacked
   branches are the biggest risk right now: every new change has to be rebased through them.
2. **Cut 0.1.0.** Move the long `## Unreleased` list in `CHANGELOG.md` under `## 0.1.0 - <date>`, tag it, and let the
   release workflow build the download ([release.md](release.md)). From then on, one changelog section per release.
3. **One version number.** `server/app/__init__.py` and `desktop/budget_buddy_desktop/__init__.py` both hold
   `__version__`; `make-release.ps1` only checks they match. Keep one `VERSION` file at the root and read it in both
   `pyproject.toml` files (and the mobile `app.json` when the phone app ships).

## 2. Code debt (server)

1. **One idea of "what a transaction is".** Whether a transaction is spending, income, a transfer, a paycheck
   deposit, a donation, a dividend, a stock trade or a sweep is worked out by chains of `NOT IN (...)` subqueries
   repeated in `services/summary.py`, `transactions.py` (the uncategorized filter), `transfer_matching.py`,
   `repeat_gifts.py`, `dividend_matching.py`, `sweeps.py` and `bank_trades.py`. Each new feature adds another link
   in every chain (and SQLite can't nest unions, which bit us once). Fix: one module, `services/transaction_roles.py`,
   with `role_conditions(...)` (or a stored `role` column kept up to date) that every caller uses. Biggest win.
2. **Dividends and bank trades are the same shape** (a payment, its sweep, a name, `dismissed`). Now that sweeps are
   shared (`services/sweeps.py`), also share "find, file, dismiss" so a third kind (interest, fees) is a small
   addition.
3. **Group the 59 flat files in `server/app/services/`** into packages that match the dashboard sections, and
   mirror them in `routers/`, `schemas/` and `tests/`:
   `ledger/` (accounts, transactions, transfers, balances), `imports/` (csv_*, activity_*, positions_csv, imports),
   `budget/` (categories, rules, learning, summary, trend, budget_engine, budget_plan), `investing/` (stock_*,
   positions, holdings, prices, bank_trades, dividends, sweeps, retirement), `tax/` (donations, gifts, deductions,
   paychecks, tax_summary, tax_export), `devices/` (pairing, devices, sync, snapshot, remote_computers, receipts).
   Do it one package per PR with `git mv` and import-only changes, and compare the test count before and after.
4. **Files near the 300-line limit:** `activity_import.py` (293), `stock_gains.py` (286), `db.py` (270),
   `tax_data/__init__.py` (269), `paychecks.py` (258), `network.py` (255). Split before the next feature touches them.
5. **Exact-dict tests.** `test_csv_import.py` compares the whole import result, so every new counter breaks it.
   Assert the fields the test is about.
6. **Tables list in `tests/test_db.py`.** It must be edited with every new table; derive it from the migrations
   instead and keep only the "models match migrations" check.

## 3. Code debt (dashboard)

1. **Group `dashboard/js/screens/` (36 files) by section:** `screens/home/`, `money/`, `budget/`, `taxes/`,
   `devices/`, with each section's parts next to its page (for example `money/transactions.js` with
   `give-to-charity.js`, `stock-trade-cell.js` and `category-picker.js`). `main.js` already lists pages by section,
   so the folders follow it one to one.
2. **Screens have no automated test.** Only the logic modules and the static safety rules are tested. Add a small
   smoke test that starts a test Home Base with demo data, opens every page in headless Edge or Chrome through the
   DevTools protocol (no packages; Node 22 has `WebSocket`) and fails on a script error or an empty page. A working
   prototype of the screenshot side was used for this hand-off.
3. **Charts on phones.** Charts are drawn 640 wide and scaled down; on a phone the text is still small. Let each
   chart take its width from its card and lay out labels for it.
4. **Small helpers to move out of screens** into tested modules: `sharesText` (bank-trades-card.js), the plural
   wording on Home, and the account-kind sets repeated in `stock-trade-cell.js` and elsewhere.

## 4. Repository layout (make it easier to find things)

| Today | Proposed | Why |
| --- | --- | --- |
| `launch/` (double-click) and `scripts/` (what they run, plus tester, developer and release tools) | `launch/` unchanged; `scripts/` split into `scripts/testing/` (demo data, test server, pairing), `scripts/dev/`, `scripts/release/` (build, install, make-release) | One look tells you who a script is for |
| `docs/guide/` (32 files, testers and users mixed) | `docs/guide/` for users only, grouped by the dashboard's sections; tester guides move to `docs/testing/` | Users never land on "start three PowerShell windows" |
| `docs/ROADMAP.md` (done and future mixed, long) | Keep only what's next; move finished milestones to `docs/history.md` | The roadmap fits on one screen |
| `docs/showcase/` | Keep; refresh screenshots each release from the smoke test above | The showcase never goes stale |
| `desktop/packaging/` (spec, installer, read-me) and `server/packaging/` | `packaging/windows/` at the root with both specs and the installer | Releasing lives in one place |
| `mobile/` (Expo app in testing, not shipped) | Keep, but say "in testing" at the top of `mobile/README.md` and in the root README until it ships | Sets expectations; phones use the browser for now |

Move files with `git mv` in small PRs, update links in the same PR, and run the markdown link check (any
`](...)` that doesn't resolve) before merging.

## 5. Product follow-ups noted along the way

- Receipt photos from a phone's browser (needs a security-reviewed upload route; the phone app does it today).
- A QR code for the "Other devices" join address, so a phone doesn't have to type it.
- Code signing for the Windows download, and HTTPS on the home network (ADR-0009's noted follow-up).
- Bank-file trades: read share counts when a broker puts them in the description; partial fills on several lines.
- Recurring gifts: a "check these" note on Home when a repeat payment to a charity had a different amount.
- An owner on paychecks and deductions (limits are per person), the 457(b) plan type, phone reminders (#21).
