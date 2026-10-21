# Budget Buddy: notes for Claude

Local-first budgeting + tax-prep app: Home Base server `server/` (Python/FastAPI/SQLite), phone app `mobile/`
(Expo), web dashboard `dashboard/`, Windows app `desktop/`, launchers `launch/`. Docs map: `docs/README.md`;
read only the `docs/dev/architecture/<topic>.md` and ADRs your task touches.

## Agents and reviewers
Agents in `.claude/agents/` (`docs/dev/workflow.md`). Storage, encryption, pairing, sync, auth or uploads →
`security-reviewer`. Budget or tax math → `finance-tax-expert`.

## Hard rules
- Never commit real financial data, keys, `.env`, databases, receipt images, or real hostnames/IPs.
- Money is integer cents. Dates are ISO `YYYY-MM-DD`. Tax-year numbers live in per-year data files with sources.
- Conventions: `docs/dev/conventions.md`.

## Docs in the same branch
Tick `docs/ROADMAP.md`, add a `CHANGELOG.md` line, update `docs/dev/architecture/<topic>.md` and the part's
README for API/data/setup changes, and a plain-English guide in `docs/guide/` (listed in its README) for
anything users see.

## Git and attribution
Local `feat/|fix/|docs/|chore/` branches; push, PR or merge only when the owner asks. No Claude trailers; PRs end
with exactly: "Built with Claude Code; designed and reviewed by @Redsuperninja."

## Commands
- Server: `cd server && .venv/Scripts/pytest` (setup: `docs/dev/testing.md`; after editing a `pyproject.toml`, run
  `scripts/dev/lock_dependencies.py`).
  The full suite takes ~5 min: run tests for what you touched, and the full suite once, in the background, before committing.
- Dashboard: `cd dashboard && node --test`
- Mobile: `cd mobile && npx tsc --noEmit && npm test`
- Desktop: `cd desktop && .venv/Scripts/pytest`
- More: `docs/dev/testing.md`
