# Dashboard

The Budget Buddy web page for the computer: plain HTML, CSS and JavaScript (ES modules). No build step, no
dependencies, nothing loaded from the internet. It fits phone screens too (a phone's browser can join like another
computer, ADR-0009): under 40rem wide, tabs scroll in one row and wider tables show each row as a small card. It is a separate part of the repo: it never imports server code and
talks to the Home Base only over its HTTP API (see [ADR-0005](../docs/adr/0005-dashboard-own-folder.md)).

## Run it

Start the Home Base (see [server/README.md](../server/README.md)) and open <http://127.0.0.1:8765/>. The server serves
this folder; edit a file and reload the page. Point the server somewhere else with `BUDGET_BUDDY_DASHBOARD_DIR`.

## Check it

```powershell
cd dashboard
node --test
```

Needs Node 22 or newer. The tests read the files with plain `fs` (no browser, no packages):
`tests/static-rules.test.js` enforces the safety rules (no `innerHTML`, no `replaceChildren(`, no inline script or
style, no internet addresses, no route strings or `fetch` outside `js/api/`, every module's imports resolve), and
`money.test.js`, `dates.test.js`, `percent.test.js`, `theme.test.js`, `view.test.js`, `folds.test.js`, `category-groups.test.js`,
`labels.test.js`, `charts.test.js`, `months.test.js`, `shares.test.js`, `pace-words.test.js` and `sweep-words.test.js`
cover the logic.

## What the server expects

- `index.html` has `<meta name="csrf-token" content="__CSRF_TOKEN__">`; the server swaps in this run's token.
- Assets are under `/static/` (`index.html`, top-level `*.css` and `js/**/*.js` are the only files served).
- No inline script or style (the Content-Security-Policy forbids them). Writes send `X-CSRF-Token`. Every request
  goes to the same address.

## Code layout

All under `js/` (each file starts with a one-line purpose):

| File | Job |
| --- | --- |
| `main.js` | Starts the dashboard: the sections (Home, Money, Budget, Taxes, Devices) and the pages in each, in order (`advanced: true` pages get a tab only in the All tools view); the join page on a computer that hasn't joined (no CSRF token); Devices only on the Budget Buddy computer |
| `router.js` | Section buttons, the page tabs under them, `#hash` routing (a page id, or a section id for its first page, plus optional choices like `#transactions?sorted=none` passed to `render` as options), `reload()` and `onLeave()` for screens |
| `api/client.js` | `fetch` wrapper: CSRF header, errors turned into plain English |
| `api/endpoints.js` | One named function per server route. The only file with URL strings |
| `dom.js` | `h()`, `fill()`, `showError()` (textContent only, never `innerHTML`), `browserStorage()` |
| `widgets.js` | `card` (with a title it folds up; `formCard` starts folded; `fold` for a folding group inside a card), `statCard`, `table` (optional power-user columns), `select`, `empty`, `note`, `aboutNote` (a folded explanation), `advanced` (marks a piece as All tools only) |
| `folds.js` | Which cards you folded, remembered in this browser (pure, tested) |
| `fold-all.js` | **Fold all** and **Open all** above a page with three or more folding cards (the router adds it) |
| `category-groups.js` | Categories by group with each group's budget totals (pure, tested) |
| `form.js` | The `form()` engine (a field with `advanced: true` shows only in All tools, so it needs a default) and `saveWithNote()` |
| `fields.js` | Shared form fields: account picker (everyday accounts first) and category picker, tax-year header (says "not tax advice" once), text-to-value helpers |
| `money.js` | Cents to dollars and typed dollars to cents (string logic, no float maths) |
| `dates.js` | Today, current month, month ranges |
| `labels.js` | Plain-English names for account types, groups and so on; `everydayFirst()` orders accounts for pickers |
| `percent.js` | Basis points to "15%" and back, "percent used" (string logic, no float maths) |
| `charts/` | Charts drawn as SVG in code, no library: `scale.js` (axis maths, pure and tested), `svg.js` (safe SVG builder), `fit.js` (draws a chart at its card's width and again on resize), `budget-bars.js` (spent against budget), `progress-rows.js` (each category's left/over with a meter), `meter.js` (meter and ring), `change-bars.js` (spending against last month), `months.js` (trend trimming, sparklines, which days to compare; pure and tested), `shares.js` (parts of a whole and bar lengths with negatives; pure and tested), `income-split.js` (where the income went), `balance-bars.js` (what you have and owe, per account), `line-chart.js` + `hover.js` (months, with a hover guide; optional shaded area), `columns.js` (a column per month, up or down), `pace-chart.js` + `pace.js` (spending pace and its maths), `chart-card.js` ("Show as table" switch, legend, lead sentence) |
| `pace-words.js` | The plain sentence above Home's Spending pace chart (pure, tested) |
| `sweep-words.js` | Plain words for the Investments page's "Deposit sweeps to check" card (pure, tested) |
| `prefs.js` | A remembered choice from a short list, shown as an attribute on `<html>` (pure, tested); used by `theme.js` and `view.js` |
| `theme.js` | Light, dark or match the computer (`data-theme`). Colors live in `app.css` as `light-dark()` pairs, the same green theme in both (`--accent` fills, `--link` is text, `--accent-soft` for meter tracks, `--raised` for a bar chart's empty track) |
| `view.js` | Simple view (default) or All tools (`data-view="all"`). `app.css` hides `.advanced` pieces in the simple view |
| `settings-menu.js` | The header's **Settings** menu with the View and Colors pickers |
| `remove-button.js` | A **Delete** (or **Remove**, **Undo**) button that asks first, then runs the removal; used on Money and Taxes screens |
| `screens/<section>/*.js` | One folder per navigation section (`home`, `money`, `budget`, `tax`, `devices`, as in `main.js`), one file per screen, each exporting `render(root, options)`, with that screen's parts beside it; `import-mapping.js`, `phone-list.js` and `give-to-charity.js` are parts of the Import, Connect phone and Transactions screens; `category-picker.js` is the category dropdown shared by Transactions and Auto-sort; `account-balance.js` is the Accounts screen's "Match your bank's balance"; `live-prices.js` is the Investments screen's live prices (ADR-0010); `bank-trades-card.js` is its list of stock trades from a bank file, with ticker, shares and price per share; `sweep-check-card.js` is its "Deposit sweeps to check" (free sweep lines with possible matches and Link, counts per account; words in `sweep-words.js`) |

To add a screen: create `screens/<section>/<name>.js` with a `render` function and add one line to its section in
`main.js`. A part used by screens in more than one section goes in `js/` (like `remove-button.js`).
Keep the top row short: add a page to an existing section rather than a new section. Keep the simple view calm:
a page, card, column or field only power users need is marked `advanced` (see `view.js`). To call a new
server route, add a function to `api/endpoints.js`.

Screens, by section: **Home** (a Get started checklist for someone new in `home-start.js`, money tiles, what needs you, spending pace (`home-pace.js`, its sentence in `pace-words.js`), where the income went, budget charts, compared with last month, month by month, left over each month
and net worth over time (`home-trends.js`), what you have and owe); **Money**: Transactions (search, filters by account, month, category and how it was sorted, a totals line, and options like `#transactions?category=3&month=2026-10` that Home's category links use; with a Charity column to
sort a payment into charity), Accounts, Investments (holdings, prices, retirement limits), Import files (bank and brokerage activity), Import history (undo an import), Receipts (photos, delete), Auto-sort (rules); **Budget**: Categories, Suggested budget;
**Taxes**: Tax summary (with a CSV download, and print styles in `app.css`), Donations, Paychecks, Stocks (with CSV import); **Devices**:
Connect phone, Other devices (`other-computers.js`: another computer or a phone's browser). `join.js` is the join page for another computer or phone
([ADR-0009](../docs/adr/0009-other-computers.md)).
