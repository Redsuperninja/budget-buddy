# Developer testing

How to check your work in each part, and what CI runs. (Testers trying Budget Buddy with demo data: see
[docs/guide/](../guide/).)

## Commands

| Part | Set up once | Check |
| --- | --- | --- |
| Server | `cd server`, `python -m venv .venv`, `.venv\Scripts\pip install -e ".[dev]"` | `.venv\Scripts\ruff check .`, `.venv\Scripts\ruff format --check .`, `.venv\Scripts\pytest` |
| Dashboard | Node 22+, nothing to install | `cd dashboard`, `node --test` |
| Phone | `cd mobile`, `npm install` | `npx tsc --noEmit` (or `npm run typecheck`), `npm test` |

On macOS/Linux use `.venv/bin/...`. Run the tests you touched first (`pytest -q path::test`,
`npm test -- <pattern>`), then the full suite.

## CI (`.github/workflows/`)

Each part has its own workflow, triggered only by changes to that part's folder (or the workflow file):

- `server-ci.yml`: Python 3.12 and 3.14; `ruff check`, `ruff format --check`, `pytest --cov`.
- `dashboard-ci.yml`: Node 22; `npm run coverage` (`node --test` with coverage; no dependencies to install).
- `mobile-ci.yml`: Node 22; `npm ci`, `npx tsc --noEmit`, `npm test -- --ci --coverage`.

## Coverage rules

CI fails when test coverage drops below these floors. Raise a floor when coverage goes up; lower one only with
a reason in the PR.

| Part | Floor | Where it's set | Check locally |
| --- | --- | --- | --- |
| Server | 94% of lines in `app/` (96% when set) | `[tool.coverage.report] fail_under` in `server/pyproject.toml` | `.venv\Scripts\pytest --cov` |
| Dashboard | 100% of lines, branches and functions in the logic modules `money.js`, `dates.js`, `percent.js` (screens need a browser, so they're checked by the static rules instead) | `coverage` script in `dashboard/package.json` | `npm run coverage` |
| Phone | statements 90%, branches 80%, functions 90%, lines 92% | `jest.coverageThreshold` in `mobile/package.json` | `npm test -- --coverage` |

A new logic module in the dashboard joins the `--test-coverage-include` list in the same PR.

## Server tests

- pytest + FastAPI `TestClient`, a temporary data folder per test, fake data only.
- **No password vault in tests.** Tests and CI keep the encryption key in memory with
  `BUDGET_BUDDY_KEY_STORE=memory` **plus** `BUDGET_BUDDY_INSECURE_TEST_KEYSTORE=1`. The key is lost when the
  process stops, so this works only on a new, empty data folder and is refused on any folder that already has
  data or a `key-fingerprint` file. `tests/conftest.py` and `server-ci.yml` set both. Never use it for real data.
- **Fake dashboard.** An autouse fixture, `fake_dashboard` in `tests/conftest.py`, writes a tiny dashboard into
  the temp folder and points `BUDGET_BUDDY_DASHBOARD_DIR` at it, so no server test reads the real `dashboard/`.
- Shared helpers: `tests/fake_phone.py` (the phone side of pairing and sync) and `tests/contract_vectors.py`
  (sync contract §4.7 vectors, tested once in `test_envelope_vectors.py`).
- When splitting test files, the test count must not change: compare `pytest --collect-only -q` before and after.

## Dashboard tests

Node's built-in runner reads the files with `fs` (no browser, no packages). `tests/static-rules.test.js`
enforces the safety rules (no `innerHTML`, no inline script or style, no internet addresses, route strings only
in `js/api/`); `money.test.js`, `dates.test.js` and `percent.test.js` cover the logic. Details: [dashboard/README.md](../../dashboard/README.md).

## Phone tests

Jest (`jest-expo` preset) and React Native Testing Library. The sync contract's test vectors and the §5.2
snapshot example are unit tests in `mobile/src/sync/__tests__/`.

## Trying it by hand with the scripts

`scripts/` starts a separate **test** Home Base (port 8766, its own data folder) and fills it with made-up
data. The Python helpers refuse to run against the real Home Base: they talk only to `127.0.0.1:8766` and need
the marker file `start-test-server.ps1` makes in the test data folder. See [scripts/README.md](../../scripts/README.md).
