# Dashboard

The Budget Buddy web page for the computer: plain HTML, CSS and JavaScript (ES modules). No build step, no
dependencies, nothing loaded from the internet. It is a separate part of the repo: it never imports server code and
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
`money.test.js`, `dates.test.js`, `percent.test.js`, `theme.test.js` and `charts.test.js` cover the logic.

## What the server expects

- `index.html` has `<meta name="csrf-token" content="__CSRF_TOKEN__">`; the server swaps in this run's token.
- Assets are under `/static/` (`index.html`, top-level `*.css` and `js/**/*.js` are the only files served).
- No inline script or style (the Content-Security-Policy forbids them). Writes send `X-CSRF-Token`. Every request
  goes to the same address.

## Code layout

All under `js/` (each file starts with a one-line purpose):

| File | Job |
| --- | --- |
| `main.js` | Starts the dashboard: the sections (Home, Money, Budget, Taxes, Phone) and the pages in each, in order |
| `router.js` | Section buttons, the page tabs under them, `#hash` routing (a page id, or a section id for its first page), `reload()` and `onLeave()` for screens |
| `api/client.js` | `fetch` wrapper: CSRF header, errors turned into plain English |
| `api/endpoints.js` | One named function per server route. The only file with URL strings |
| `dom.js` | `h()`, `fill()`, `showError()` (textContent only, never `innerHTML`) |
| `widgets.js` | `card`, `statCard`, `table`, `select`, `empty`, `note` |
| `form.js` | The `form()` engine and `saveWithNote()` |
| `fields.js` | Shared form fields: account and category pickers, tax-year header, text-to-value helpers |
| `money.js` | Cents to dollars and typed dollars to cents (string logic, no float maths) |
| `dates.js` | Today, current month, month ranges |
| `labels.js` | Plain-English names for account types, groups and so on |
| `percent.js` | Basis points to "15%" and back, "percent used" (string logic, no float maths) |
| `charts/` | Charts drawn as SVG in code, no library: `scale.js` (axis maths, pure and tested), `svg.js` (safe SVG builder), `budget-bars.js` (spent against budget), `line-chart.js` + `hover.js` (months, with a hover guide), `chart-card.js` ("Show as table" switch and legend) |
| `theme.js`, `theme-picker.js` | Light, dark or match the computer: the saved choice (pure, tested) and the header picker. Colors live in `app.css` as `light-dark()` pairs |
| `screens/*.js` | One file per screen, each exporting `render(root, options)`; `import-mapping.js`, `phone-list.js` and `give-to-charity.js` are parts of the Import, Connect phone and Transactions screens |

To add a screen: create `screens/<name>.js` with a `render` function and add one line to its section in `main.js`.
Keep the top row short: add a page to an existing section rather than a new section. To call a new
server route, add a function to `api/endpoints.js`.

Screens, by section: **Home** (monthly summary, charts and balances); **Money**: Transactions (with a Charity column to
sort a payment into charity), Accounts, Import bank file, Auto-sort (rules); **Budget**: Categories, Suggested budget;
**Taxes**: Tax summary (with a CSV download, and print styles in `app.css`), Donations, Paychecks, Stocks; **Phone**:
Connect phone.
