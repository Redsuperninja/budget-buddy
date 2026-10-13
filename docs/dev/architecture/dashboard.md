# Dashboard (how the server serves it)

The dashboard is its own part, [`dashboard/`](../../../dashboard/README.md): plain HTML, CSS and JavaScript, no
build step, no internet requests (system fonts, local files only). It talks to the server only through the HTTP
API ([ADR-0005](../../adr/0005-dashboard-own-folder.md)). Its screens cover accounts, transactions, categories,
bank CSV import, paychecks, donations, stocks and connecting a phone. Its code layout and tests are in
`dashboard/README.md`; this page is the server half.

## Finding and serving the files (`app/dashboard_files.py`, `routers/dashboard.py`)

- At startup the server looks for `BUDGET_BUDDY_DASHBOARD_DIR`, else `<repo>/dashboard` (worked out from the
  code's location, not the current directory), and builds an **allowlist** once: `index.html`, top-level
  `*.css` and `js/**/*.js`. No symlinks are followed, every resolved path must stay inside the folder,
  dotfiles, `tests/` and `package.json` are never listed, and file count and size are capped. The check is
  repeated when a file is read. A request for a file that isn't listed rebuilds the list with the same rules (at
  most every 2 seconds), so files added by an update are served without a restart.
- Until `main.js` runs, the page shows "Loading Budget Buddy..." with a hint to restart, so a script that fails
  to load never leaves a blank page.
- `GET /` serves `index.html`; `GET /static/{path}` serves the other allowlisted files. The page loads
  `/static/js/main.js`.
- **API-only mode.** If the folder is missing, isn't a folder, or has no `index.html`, the server logs one
  plain-English warning, `/` returns a small 404 page ("the dashboard files weren't found") with the same
  headers, `/static/*` returns 404, and every `/api/...` route works. A non-editable `pip install` doesn't
  include `dashboard/`, so it runs API-only until the installer (roadmap #22) ships it.

## Serving contract (both sides test their half)

- `index.html` contains `<meta name="csrf-token" content="__CSRF_TOKEN__">`; the server swaps in this run's token.
- Assets live under `/static/`. No inline script or style. Every request is same-origin.
- Writes send the token back in `X-CSRF-Token`.

## Headers

Every page response carries a strict Content-Security-Policy (`default-src 'self'`, no inline script,
`frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and the HTML is
`Cache-Control: no-store`. There are no CORS headers, so other websites can't read anything.

## CSRF and DNS rebinding (issue #4)

Met by `LocalAccessMiddleware` (`app/network.py`) plus the CSP:

- Host allowlist and loopback-only peer ([server.md](server.md)).
- `Origin` must match on every write.
- A per-run CSRF token (random, kept in `app.state`, never logged) must come back in `X-CSRF-Token`, compared
  in constant time. Failure is 403 `bad_origin`.
- The page gets the token from its meta tag; the helper scripts get it from `GET /api/local/csrf-token`
  (this computer only).

## Rules for dashboard code

- Build the page with `textContent` only, never `innerHTML` with API data.
- Every route string lives in `dashboard/js/api/endpoints.js`.
- The pairing QR is drawn on the server (`segno`) and returned as SVG; the dashboard just shows it.

Server tests use a fake dashboard folder (`fake_dashboard` in `server/tests/conftest.py`), never the real one
([../testing.md](../testing.md)).

## Simple view and All tools

The dashboard starts in a **simple view** so a first-time user sees only everyday pages and controls. Power-user
pieces (Import history, Auto-sort, Find transfers, the gift and stock-trade column, transaction type, positions
import, live price settings) carry the `advanced` class; `app.css` hides them unless `<html data-view="all">`,
which the header **Settings** menu sets (`js/view.js`, remembered in `localStorage` per browser). It is a display
choice only: the API, the data and every route are the same in both views, and a link to a hidden page still
opens it. Home also shows a **Get started** checklist (`screens/home-start.js`) until there are accounts,
transactions and budgets, and hides its charts until the first transaction.

## Folding cards

Every card with a title is a `<details>` (`widgets.js` `foldCard`): clicking the title folds it to one line. A
card's open or folded state is remembered per browser in `localStorage` (`js/folds.js`, pure and covered 100%),
keyed by its title without digits, so "Dividends in 2026" keeps its state next year. Only a change from what's
remembered is saved, so a card's default can still change later. `formCard` starts folded (forms that add
something; "Add an account" stays open until there is one), and `aboutNote` folds a long explanation under
**About these numbers** (never a warning or the "not tax advice" line). In print, `::details-content` shows every
folded card. A card without a title is a plain `<section>`. On a page with three or more folding cards the router adds
**Fold all** and **Open all** above it (`js/fold-all.js`); they set each card's `open`, so each remembers it. `fold()` is the
folding box itself, for groups inside a card: Categories lists one per group (`category-groups.js`, pure and
covered 100%, adds up amount and percentage budgets apart, never counting a percentage category's stored cents).

## Charts

Home shows money tiles with SVG meters (`screens/home-tiles.js`; inline styles are blocked by the CSP), a "needs
your attention" list, where the income went (`charts/income-split.js`: one bar split into needs, wants, savings and
a neutral gray left over), spending against budget (by group and by category), spending against last month
(`charts/change-bars.js`: more = series 2 to the right, less = series 1 to the left, always with "more" or "less"
in words; the same days of last month while the month is going, via the summary's `through`), month by month (from
the first month with activity, up to 12) of money in,
spending and saving, and balances as bars either side of zero with net worth (`charts/balance-bars.js`; have =
series 1, owe = series 2). Each money tile has a sparkline of its own number over the same months. "Needs your attention" adds needs and
wants categories over budget (`category-groups.js` `overBudget`, with the percent over as the badge, "<1%" rather
than "+0%"; percentage budgets are skipped while the month is going and budgets follow actual income, since a share of
part of a month's pay isn't the month's budget), and the
toolbar says when a file was last imported (`imports` list; its UTC `created_at` becomes a local date with
`dates.localDate`). Category bars link to `#transactions?category=&month=` (an SVG `<a>` left out of the Tab order;
the chart's table has the same links for keyboards and screen readers).
Their maths is in `charts/shares.js` and `charts/months.js`, covered 100% like `scale.js`. They are SVG built in code (`js/charts/`), with no chart library and nothing loaded from the internet, so
the CSP and the safety tests are unchanged; the only web address in them is the SVG namespace in `js/charts/svg.js`,
which the static test allows by exact match. Every chart has a "Show as table" switch and an `aria-label`. The
three series colors are a color-blind-checked set for both light and dark (checked with the dataviz palette
validator against the card colors); text never uses a series color, and the line ends carry the series names.

Light and dark use the same palette, stepped for each background, never flipped: `--accent` is the one blue that
fills buttons and the current section, with white text in both (4.6:1 or more), and `--link` is that blue as text
on the page (5:1 or more on the page and on cards). Good, bad and the yellow note keep their hue in both.
