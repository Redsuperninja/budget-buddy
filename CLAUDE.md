# Budget Buddy: notes for Claude

Local-first budgeting + tax-prep app. Home Base server in `server/` (Python/FastAPI/SQLite), phone app in
`mobile/` (Expo). Read `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, and `docs/adr/` first.

## How work is done
- Work is split across the specialized agents in `.claude/agents/`; see `docs/WORKFLOW.md`.
- One roadmap item = one small PR on a `feat/|fix/|docs/|chore/` branch. Never commit to `main` directly.
- Any change to storage, encryption, pairing, sync, auth, or uploads gets a `security-reviewer` pass.
  Any change to budget or tax math gets a `finance-tax-expert` pass.

## Hard rules
- Never commit real financial data, keys, tokens, `.env`, databases, or receipt images.
- Money is integer cents. Dates are ISO `YYYY-MM-DD`.
- Tax-year numbers live in per-year data files with sources, not in logic.
- User-facing text is plain English for non-technical users.

## Commands
- Server: `cd server && python -m venv .venv && .venv/Scripts/pip install -e ".[dev]" && .venv/Scripts/pytest`
- Mobile: `cd mobile && npm install && npx tsc --noEmit && npm test`
