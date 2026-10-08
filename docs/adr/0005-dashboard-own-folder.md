# ADR-0005: The dashboard is its own top-level folder

**Status:** Accepted, 2026-10-07

## Context
The web dashboard lived inside the server's Python package (`server/app/dashboard/`). The owner wants
`dashboard/`, `server/` and `mobile/` to be separate parts, so changing or migrating one doesn't touch the
others. The dashboard is plain HTML, CSS and JavaScript with no build step, and already talks to the server only
over HTTP.

## Decision
- The dashboard moves to top-level `dashboard/`. It is no longer a Python package and the server never imports it.
- The server finds the folder at startup: `BUDGET_BUDDY_DASHBOARD_DIR` if set, otherwise `<repo>/dashboard`
  (worked out from the code's location, not the current directory).
- It serves only an allowlist built once at startup: `index.html`, top-level `*.css`, and `js/**/*.js`. No
  symlinks are followed, every path must stay inside the folder, dotfiles, `tests/` and `package.json` are
  never listed, and file count and size are capped. The check is repeated when a file is read.
- If the folder is missing or has no `index.html`, the server logs one plain-English warning and runs API only:
  `/` gives a friendly 404 page, `/api/...` is unaffected.
- URLs, the Content-Security-Policy, the other security headers and the CSRF token flow are unchanged.
- The dashboard keeps every route string in one file (`dashboard/js/api/endpoints.js`). Its safety rules
  (no `innerHTML`, no inline script, no internet addresses) are checked by its own `node --test` tests; the server's
  tests use a fake dashboard folder and check the serving half (headers, allowlist, CSRF meta tag).

## Consequences
- A non-editable `pip install` of the server doesn't include `dashboard/`, so it serves the API only. That is
  accepted until roadmap #22, whose installer must ship `dashboard/` beside the server.
- Still no build step and no JavaScript dependencies.
- The server works headless (for example on a machine with no browser use).
- `dashboard/` has its own CI workflow. Server CI doesn't run on dashboard-only changes.
- Code shared by two parts (for example money formatting) is copied, each with its own tests.
