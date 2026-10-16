# Developer testing

How to check your work in each part, and what CI runs. (Testers trying Budget Buddy with demo data: see
[docs/testing/](../testing/README.md).)

## Commands

| Part | Set up once | Check |
| --- | --- | --- |
| Server | `cd server`, `python -m venv .venv`, `.venv\Scripts\pip install -e ".[dev]"` | `.venv\Scripts\ruff check .`, `.venv\Scripts\ruff format --check .`, `.venv\Scripts\pytest` |
| Dashboard | Node 22+, nothing to install | `cd dashboard`, `node --test` |
| Phone | `cd mobile`, `npm install` | `npx tsc --noEmit` (or `npm run typecheck`), `npm test` |
| Desktop (Windows) | `cd desktop`, `py -3 -m venv .venv`, `.venv\Scripts\pip install -e ".[dev]"` | `.venv\Scripts\ruff check .`, `.venv\Scripts\pytest --cov` |

On macOS/Linux use `.venv/bin/...`. Run the tests you touched first (`pytest -q path::test`,
`npm test -- <pattern>`), then the full suite.

**Everything at once:** `powershell -ExecutionPolicy Bypass -File scripts\dev\check-all.ps1` runs every part's
checks (the same as CI) and lists which passed. Run it before pushing or merging, and always for a change one part
makes that another relies on (below).

## Checks between parts

Parts only talk over HTTP, so a change in one can break another without failing that part's own tests. These
tests catch it; each reads the other side's files or a published example, never its code:

| What could break | Checked by |
| --- | --- |
| A route the dashboard, phone app, desktop app or scripts call is renamed or removed | `server/tests/test_callers_match_routes.py` (reads `dashboard/js/api/endpoints.js` and the others' source) |
| The phone snapshot gains, loses or retypes a field | The example in [sync-contract/05-snapshot.md](../api/sync-contract/05-snapshot.md) §5.2, read by `server/tests/devices/test_snapshot_contract_example.py` and `mobile/src/sync/__tests__/snapshot.test.ts` |
| Pairing and sync encryption | The §4.7 vectors, in `server/tests/contract_vectors.py` and the phone's `pairing.test.ts` |
| The desktop app's copies of the data folder rule, the default port and the "really Budget Buddy" proof | The example in [desktop-handshake.md](../api/desktop-handshake.md), read by `server/tests/test_desktop_handshake.py` and `desktop/tests/test_genuine.py` |
| A dashboard screen breaks when it runs (a moved file, a renamed field the screen reads) | `scripts\dev\check-pages.ps1`: every page in a headless browser against a Home Base with demo data (needs Edge or Chrome; not in CI yet) |
| The dashboard outgrows what the Home Base serves (past its file limit the page disappears) | `test_the_real_dashboard_is_served_whole_with_room_to_grow` in `server/tests/test_dashboard_serving.py` |

Changing one of these on purpose: change the published example (or route) and both sides in the same branch.

## CI (`.github/workflows/`)

**Paused until 2026-11-22:** the four workflows below only run by hand (GitHub, Actions, pick one, **Run
workflow**), so PRs can merge while CI is being fixed up. Run each part's checks locally before merging. To bring
CI back, delete `workflow_dispatch:` in each file and uncomment the lines under it.

Once back, each part has its own workflow, run on pull requests **into `main`** and on pushes to `main` (never on
stacked branches), and only when that part's folder, the workflow file, or what its checks between parts read
changed (the server's also on `dashboard/`, `mobile/src/`, `desktop/budget_buddy_desktop/`, `scripts/` and
`docs/api/`; the phone's and the desktop's also on `docs/api/`):

- `server-ci.yml`: Python 3.12 and 3.14; `ruff check`, `ruff format --check`, `pytest --cov`.
- `dashboard-ci.yml`: Node 22; `npm run coverage` (`node --test` with coverage; no dependencies to install).
- `mobile-ci.yml`: Node 22; `npm ci`, `npx tsc --noEmit`, `npm test -- --ci --coverage`.
- `desktop-ci.yml`: Windows, Python 3.12 and 3.14; `ruff check`, `ruff format --check`, `pytest --cov`.

## Coverage rules

CI fails when test coverage drops below these floors. Raise a floor when coverage goes up; lower one only with
a reason in the PR.

| Part | Floor | Where it's set | Check locally |
| --- | --- | --- | --- |
| Server | 94% of lines in `app/` (96% when set) | `[tool.coverage.report] fail_under` in `server/pyproject.toml` | `.venv\Scripts\pytest --cov` |
| Dashboard | 100% of lines, branches and functions in the logic modules, the `--test-coverage-include` list in `dashboard/package.json` (screens need a browser, so they're checked by the static rules instead) | `coverage` script in `dashboard/package.json` | `npm run coverage` |
| Desktop | 95% of lines in `budget_buddy_desktop/` (98% when set; the on-screen tray loop is checked by hand) | `[tool.coverage.report] fail_under` in `desktop/pyproject.toml` | `.venv\Scripts\pytest --cov` |
| Phone | statements 90%, branches 80%, functions 90%, lines 92% | `jest.coverageThreshold` in `mobile/package.json` | `npm test -- --coverage` |

A new logic module in the dashboard joins the `--test-coverage-include` list in the same PR.

## Server tests

- pytest + FastAPI `TestClient`, a temporary data folder per test, fake data only.
- **No password vault in tests.** Tests and CI keep the encryption key in memory with
  `BUDGET_BUDDY_KEY_STORE=memory` **plus** `BUDGET_BUDDY_INSECURE_TEST_KEYSTORE=1`. The key is lost when the
  process stops, so this works only on a new, empty data folder and is refused on any folder that already has
  data or a `key-fingerprint` file. `tests/conftest.py` and `server-ci.yml` set both. Never use it for real data.
- **Fake dashboard.** An autouse fixture, `fake_dashboard` in `tests/conftest.py`, writes a tiny dashboard into
  the temp folder and points `BUDGET_BUDDY_DASHBOARD_DIR` at it, so server tests don't read the real `dashboard/`
  (except the size check above).
- Shared helpers: `tests/fake_phone.py` (the phone side of pairing and sync) and `tests/contract_vectors.py`
  (sync contract §4.7 vectors, tested once in `test_envelope_vectors.py`).
- When splitting test files, the test count must not change: compare `pytest --collect-only -q` before and after.

## Dashboard tests

Node's built-in runner reads the files with `fs` (no browser, no packages). `tests/static-rules.test.js`
enforces the safety rules (no `innerHTML`, no inline script or style, no internet addresses, route strings only
in `js/api/`); the other test files cover the logic modules (the list is in
[dashboard/README.md](../../dashboard/README.md)). The screens themselves run in a real browser in
`scripts\dev\check-pages.ps1` (above).

## Phone tests

Jest (`jest-expo` preset) and React Native Testing Library. The sync contract's test vectors and the §5.2
snapshot example are unit tests in `mobile/src/sync/__tests__/`.

## Trying it by hand with the scripts

`scripts/` starts a separate **test** Home Base (port 8766, its own data folder) and fills it with made-up
data. The Python helpers refuse to run against the real Home Base: they talk only to `127.0.0.1:8766` and need
the marker file `start_test_server.py` makes in the test data folder. See [scripts/README.md](../../scripts/README.md).
