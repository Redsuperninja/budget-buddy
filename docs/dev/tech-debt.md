# Tech debt and restructuring plan

A hand-off list (2026-10-09): what to clean up so Budget Buddy stays easy to change, and how to reorganize the
repository so a newcomer can find things. Each numbered item is sized as one small PR, in a sensible order. Nothing
here changes what the app does.

## 1. Before anything else

1. ~~**Merge the open stack**~~ Done: the stacked branches were merged bottom-first (#125 to #160,
   [workflow.md](workflow.md#merging-a-stack-safely)).
2. **Cut 0.1.0.** Move the long `## Unreleased` list in `CHANGELOG.md` under `## 0.1.0 - <date>`, tag it, and let the
   release workflow build the download ([release.md](release.md)). From then on, one changelog section per release.
3. ~~**One version number.**~~ Done: `server/app/__init__.py` holds the only `__version__`; the desktop package has a
   fixed placeholder (it never shows its version), and `make-release.ps1` and the release workflow read the server's.
   (A root `VERSION` file doesn't work: setuptools won't read files outside a part's folder.)

## 2. Code debt (server)

1. ~~**One idea of "what a transaction is".**~~ Done: `services/ledger/transaction_roles.py` holds every role (paycheck
   deposit, donation, stock trade, bank-file trade, dividend, sweep) and `none_of(...)`, and every query uses it
   ([ledger.md](architecture/ledger.md#transaction-roles)). A stored `role` column wasn't needed.
2. **Dividends and bank trades are the same shape** (a payment, its sweep, a name, `dismissed`). Now that sweeps are
   shared (`services/investing/sweeps.py`), also share "find, file, dismiss" so a third kind (interest, fees) is a small
   addition.
3. **Done: grouped the 59 flat files in `server/app/services/`** into packages that match the dashboard sections, and
   mirror them in `routers/`, `schemas/` and `tests/`:
   `ledger/` (accounts, transactions, transfers, balances), `imports/` (csv_*, activity_*, positions_csv, imports),
   `budget/` (categories, rules, learning, summary, trend, budget_engine, budget_plan), `investing/` (stock_*,
   positions, holdings, prices, bank_trades, dividends, sweeps, retirement), `tax/` (donations, gifts, deductions,
   paychecks, tax_summary, tax_export), `devices/` (pairing, devices, sync, snapshot, remote_computers, receipts).
   Do it one package per PR with `git mv` and import-only changes, and compare the test count before and after.
4. **Files near the 300-line limit:** `activity_import.py` (293), `stock_gains.py` (286), `db.py` (270),
   `tax_data/__init__.py` (269), `paychecks.py` (258), `network.py` (255). Split before the next feature touches them.
5. **Exact-dict tests.** `tests/imports/test_csv_import.py` compares the whole import result, so every new counter breaks it.
   Assert the fields the test is about.
6. **Tables list in `tests/test_db.py`.** It must be edited with every new table; derive it from the migrations
   instead and keep only the "models match migrations" check.
7. **Repeated code found in the 2026-10-14 review** (each a small shared helper):
   - the "rows couldn't be read" refusal and `PREVIEW_ROWS`/`MAX_PROBLEM_ROWS` in `imports/csv_import.py`,
     `activity_import.py` and `stock_import.py` (the wording has drifted): one `refuse_invalid_rows(...)`;
   - the finders run in sequence (`find_dividends`, `find_trades`, `match_transfers`, `repeat_gifts`) in both
     importers, `routers/ledger/transactions.py` and `match_again.py`: one `run_finders(session, ids)` (the activity
     import skips `repeat_gifts`; decide whether on purpose);
   - the whole-word regex wrapper (`(?<![a-z])...(?![a-z])`) rebuilt in `bank_trades.py`, `dividend_matching.py`,
     `sweeps.py`, `pay_deposits.py`, `retirement.py`, and "name before the keyword" in three finders: an `app/words.py`;
   - `dt.date(year, 1, 1), dt.date(year, 12, 31)` in about nine tax/investing files: a public `year_range(year)`;
   - "not dismissed and no sweep yet" in `bank_trades.py`, `combined_sweeps.py`, `dividend_matching.py` and
     `sweep_check.py`: one `unlinked(model)` in `investing/sweeps.py`;
   - the test-server setup repeated in `scripts/testing/load_demo_data.py`, `pair_phone.py` and `import_csv.py`: a
     `connect_test_server(port)` in `_local_api.py`.

## 3. Code debt (dashboard)

1. **Done: grouped `dashboard/js/screens/` (36 files) by section:** `screens/home/`, `money/`, `budget/`, `tax/`,
   `devices/`, with each section's parts next to its page (for example `money/transactions.js` with
   `give-to-charity.js`, `stock-trade-cell.js` and `category-picker.js`). `main.js` already lists pages by section,
   so the folders follow it one to one.
2. **Done (locally, `scripts\dev\check-pages.ps1`; not in CI yet): screens have no automated test.** Only the logic modules and the static safety rules are tested. Add a small
   smoke test that starts a test Home Base with demo data, opens every page in headless Edge or Chrome through the
   DevTools protocol (no packages; Node 22 has `WebSocket`) and fails on a script error or an empty page. A working
   prototype of the screenshot side was used for this hand-off.
3. ~~**Charts on phones.**~~ Done (#130): each chart is drawn at its card's width and redrawn when it changes
   (`charts/fit.js`), so its text is its real size on a phone.
4. **Small helpers to move out of screens** into tested modules: `sharesText` (bank-trades-card.js), the plural
   wording on Home, and the account-kind sets repeated in `stock-trade-cell.js`, `activity-import.js` and the "card or
   loan" check twice in `money.js` (move to `labels.js`).
5. **Buttons that run an action** (disable, await, show the result or error, enable again) are written out in about
   twelve handlers; `remove-button.js` already does it for Delete. Generalise it into `action-button.js`, so no
   button can forget its error handling again (four did, fixed 2026-10-14).
6. **The three CSV import cards** (`money/import.js`, `money/activity-import.js`, `tax/stock-import.js`, plus
   `money/positions-card.js`) share a file picker, a preview button, the "skip rows with a problem" choice and the
   problems table: a `csv-upload.js`.

## 3b. Code debt (phone)

1. **Shared form and list pieces:** `app/pair.tsx` copies `TextField`'s input style (`components/Field.tsx`); a list
   row (title, muted subtitle, value, hairline) is written out in `app/index.tsx`, `AccountsList.tsx`, `app/taxes.tsx`
   and `receipts/WaitingReceipts.tsx`. Add `ListRow` and a muted `SmallText` next to `BodyText`, and a `lineHeight`
   in `theme.ts`.
2. **Exported only for tests:** `categoriesById` (`lib/budget.ts`; use it in `transactionCategoryLabel` or drop it),
   `isSnapshot` (`sync/snapshot.ts`).

## 4. Repository layout (make it easier to find things)

| Today | Proposed | Why |
| --- | --- | --- |
| Done: `launch/` (double-click) and `scripts/` (what they run, plus tester, developer and release tools) | `launch/` unchanged; `scripts/` split into `scripts/testing/` (demo data, test server, pairing), `scripts/dev/`, `scripts/release/` (build, install, make-release) | One look tells you who a script is for |
| Partly done (tester guides moved; user guides stay one folder, grouped by section in its index): `docs/guide/` (32 files, testers and users mixed) | `docs/guide/` for users only, grouped by the dashboard's sections; tester guides move to `docs/testing/` | Users never land on "start three PowerShell windows" |
| `docs/ROADMAP.md` (done and future mixed, long) | Keep only what's next; move finished milestones to `docs/history.md` | The roadmap fits on one screen |
| `docs/showcase/` | Keep; refresh screenshots each release from the smoke test above | The showcase never goes stale |
| Done: moved to `packaging/windows/` (#142) | `packaging/windows/` at the root with both specs and the installer | Releasing lives in one place |
| `mobile/` (Expo app in testing, not shipped) | ~~Say "in testing" at the top of `mobile/README.md` and in the root README until it ships~~ | Done (2026-10-14) |

Move files with `git mv` in small PRs, update links in the same PR, and run the markdown link check (any
`](...)` that doesn't resolve) before merging.

## 5. Product follow-ups noted along the way

- Receipt photos from a phone's browser (needs a security-reviewed upload route; the phone app does it today).
- A QR code for the "Other devices" join address, so a phone doesn't have to type it.
- Code signing for the Windows download, and HTTPS on the home network (ADR-0009's noted follow-up).
- Bank-file trades: read share counts when a broker puts them in the description; partial fills on several lines.
- Recurring gifts: a "check these" note on Home when a repeat payment to a charity had a different amount.
- An owner on paychecks and deductions (limits are per person), the 457(b) plan type.
- From the reviews (should-fix, not done): Roth IRA deposits made January to April 15 for the year before, when
  the description names that year, should count toward that year (`services/investing/retirement.py`); a refund of an excess
  contribution should be taken off; the Receipts page's "Download photo" link should use `?download=true` when a
  photo can't be shown.
