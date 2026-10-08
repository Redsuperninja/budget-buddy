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
`money.test.js` and `dates.test.js` cover the money and date logic.

## What the server expects

- `index.html` has `<meta name="csrf-token" content="__CSRF_TOKEN__">`; the server swaps in this run's token.
- Assets are under `/static/` (`index.html`, top-level `*.css` and `js/**/*.js` are the only files served).
- No inline script or style (the Content-Security-Policy forbids them). Writes send `X-CSRF-Token`. Every request
  goes to the same address.

## Code layout

All under `js/` (each file starts with a one-line purpose):

| File | Job |
| --- | --- |
| `main.js` | Starts the dashboard: the list of screens, in navigation order |
| `router.js` | Navigation buttons, `#hash` routing, `reload()` and `onLeave()` for screens |
| `api/client.js` | `fetch` wrapper: CSRF header, errors turned into plain English |
| `api/endpoints.js` | One named function per server route. The only file with URL strings |
| `dom.js` | `h()`, `fill()`, `showError()` (textContent only, never `innerHTML`) |
| `widgets.js` | `card`, `statCard`, `table`, `select`, `empty`, `note` |
| `form.js` | The `form()` engine and `saveWithNote()` |
| `fields.js` | Shared form fields: account and category pickers, tax-year header, text-to-value helpers |
| `money.js` | Cents to dollars and typed dollars to cents (string logic, no float maths) |
| `dates.js` | Today, current month, month ranges |
| `labels.js` | Plain-English names for account types, groups and so on |
| `screens/*.js` | One file per screen, each exporting `render(root, options)`; `import-mapping.js` and `phone-list.js` are parts of the Import and Connect phone screens |

To add a screen: create `screens/<name>.js` with a `render` function and add one line to `main.js`. To call a new
server route, add a function to `api/endpoints.js`.

Screens: Home (monthly summary and balances), Accounts, Transactions, Categories, Suggested budget, Auto-sort (rules), Import bank file, Connect phone,
Paychecks, Donations, Stocks.
