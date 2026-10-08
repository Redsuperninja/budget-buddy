# Budget Buddy: notes for Claude

Local-first budgeting + tax-prep app. Home Base server in `server/` (Python/FastAPI/SQLite), phone app in
`mobile/` (Expo), web dashboard in `dashboard/`, Windows app in `desktop/`, double-click launchers in `launch/`. Read `docs/dev/architecture/README.md`, `docs/ROADMAP.md`, and
`docs/adr/` first (map of all docs: `docs/README.md`).

## How work is done
- Work is split across the specialized agents in `.claude/agents/`; see `docs/dev/workflow.md`.
- One roadmap item = one small local branch (`feat/|fix/|docs/|chore/`). Never commit to `main` directly.
- Any change to storage, encryption, pairing, sync, auth, or uploads gets a `security-reviewer` pass.
  Any change to budget or tax math gets a `finance-tax-expert` pass.

## Hard rules
- Never commit real financial data, keys, tokens, `.env`, databases, or receipt images.
- Money is integer cents. Dates are ISO `YYYY-MM-DD`.
- Tax-year numbers live in per-year data files with sources, not in logic.
- User-facing text is plain English for non-technical users.
- Small files, no repetition: one job per file, reuse shared helpers, one topic per doc. See `docs/dev/conventions.md`.
- Attribution: code is built by Claude, designed and reviewed by the owner (stated in README and `docs/dev/workflow.md`).
  Do NOT add `Co-Authored-By: Claude` trailers or "Generated with Claude Code" lines. PR descriptions end with
  exactly one line: "Built with Claude Code; designed and reviewed by @Redsuperninja."
- Commit to local branches by default. Push, open PRs, or merge only when the owner asks for it.
- Docs ship with the code, in the same branch: tick `docs/ROADMAP.md`, add a `CHANGELOG.md` line, update
  the matching `docs/dev/architecture/<topic>.md` and the part's README (`server/`, `dashboard/`, `mobile/`,
  `desktop/`, `scripts/`) for any API, data, or setup change, keep the root `README.md` accurate, and add or update a
  plain-English guide in `docs/guide/` (listed in `docs/guide/README.md`) for any user-facing feature.

## Commands
- Server: `cd server && python -m venv .venv && .venv/Scripts/pip install -e ".[dev]" && .venv/Scripts/pytest`
- Dashboard: `cd dashboard && node --test`
- Mobile: `cd mobile && npm install && npx tsc --noEmit && npm test`
- Desktop (Windows): `cd desktop && py -3 -m venv .venv && .venv/Scripts/pip install -e ".[dev]" && .venv/Scripts/pytest`
- More (CI, test-only key store, fake dashboard): `docs/dev/testing.md`
