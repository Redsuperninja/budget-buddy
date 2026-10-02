# How this project is built and managed

Budget Buddy is built by a small team of **specialized AI agents** (Claude Code subagents) with a human in charge.
Each agent has one job, a written brief, and limited tools, so it's always clear who did what and why.
Agent briefs live in [`.claude/agents/`](../.claude/agents). They are plain text, so you can read and edit them.

## The team

| Agent | Job | Can edit code? |
| --- | --- | --- |
| `architect` | Breaks features into small PRs, keeps ARCHITECTURE/ROADMAP/ADRs current | Docs only |
| `backend-engineer` | Home Base server (Python/FastAPI/SQLite) | Yes (`server/`) |
| `mobile-engineer` | Phone app (Expo/React Native) | Yes (`mobile/`) |
| `finance-tax-expert` | Budget math, tax categories & rules, checks correctness | Yes (budget/tax modules + tests) |
| `security-reviewer` | Reviews every PR touching data, sync, auth or storage | No, review only |
| `test-engineer` | Adds/repairs tests, keeps CI green | Yes (tests) |
| `docs-writer` | Plain-English guides for non-technical users | Docs only |
| `release-manager` | Branches, commits, small PRs, changelog | Git/GitHub only |

## The loop for every change

1. **Plan:** `architect` picks the next roadmap item and writes a short task (goal, files, acceptance criteria).
2. **Build:** the owning engineer agent implements it on a branch `feat/<short-name>`, with tests.
3. **Check:** `test-engineer` runs the tests; `security-reviewer` reviews if data/sync/auth/storage is touched;
   `finance-tax-expert` reviews if money math or tax logic is touched.
4. **Ship:** `release-manager` opens a **small PR** (aim for < ~400 changed lines) with a plain-English summary.
5. **Merge:** after CI passes. The roadmap checkbox gets ticked in the same PR.

## Rules every agent follows
- Small PRs, one purpose each. Push early, push often.
- **Never commit real personal/financial data**, keys, tokens, or `.env` files. Test data is fake.
- Money is integer cents. Dates are ISO `YYYY-MM-DD`.
- Every PR explains *what* and *why* in words a non-programmer can follow.
- Big decisions get an ADR in `docs/adr/` (one page: context, decision, consequences).

## Using the agents yourself
In Claude Code, from this folder, ask for an agent by name, e.g.:

> "Use the finance-tax-expert agent to add support for HSA contributions."

> "Have the security-reviewer agent review PR #12."
