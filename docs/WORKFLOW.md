# How this project is built and managed

Budget Buddy is built by a small team of **specialized AI agents** (Claude Code subagents) with a human in charge.
Each agent has one job, a written brief, and limited tools, so it's always clear who did what and why.
Agent briefs live in [`.claude/agents/`](../.claude/agents). They are plain text, so you can read and edit them.

## The team

| Agent | Job | Can edit code? | Model |
| --- | --- | --- | --- |
| `architect` | Breaks features into small PRs, keeps ARCHITECTURE/ROADMAP/ADRs current | Docs only | Opus |
| `backend-engineer` | Home Base server (Python/FastAPI/SQLite) | Yes (`server/`) | Sonnet |
| `mobile-engineer` | Phone app (Expo/React Native) | Yes (`mobile/`) | Sonnet |
| `finance-tax-expert` | Budget math, tax categories & rules, checks correctness | Yes (budget/tax modules + tests) | Opus |
| `security-reviewer` | Reviews every PR touching data, sync, auth or storage | No, review only | Opus |
| `test-engineer` | Adds/repairs tests, keeps CI green | Yes (tests) | Sonnet |
| `docs-writer` | Plain-English guides for non-technical users | Docs only | Haiku |
| `release-manager` | Branches, commits, small PRs, changelog | Git/GitHub only | Haiku |

The model matches the job. Judgment-heavy work (planning, security, tax math) gets the strongest model.
Routine coding and tests get a mid-size one. Docs and git chores get the fastest, cheapest one.
Agents read only the files their task needs and reply with short summaries, which keeps token use low.

**Who does what:** the code is built by [Claude Code](https://claude.com/claude-code) (Anthropic) through these agents.
The design and all reviews come from the project owner. Agents commit to local branches only. The owner reviews
those commits and decides which ones become pull requests and get merged on GitHub.

## The loop for every change

1. **Plan:** `architect` picks the next roadmap item and writes a short task (goal, files, acceptance criteria).
2. **Build:** the owning engineer agent implements it on a branch `feat/<short-name>`, with tests and docs:
   ARCHITECTURE.md and the server/mobile README for API or data changes, plus a plain-English guide in
   `docs/guide/` for anything a user will see.
3. **Check:** `test-engineer` runs the tests; `security-reviewer` reviews if data/sync/auth/storage is touched;
   `finance-tax-expert` reviews if money math or tax logic is touched.
4. **Commit:** `release-manager` commits the work to its local branch (aim for < ~400 changed lines), ticks the
   roadmap box, and adds a changelog line. Nothing is pushed.
5. **Owner review:** the project owner reviews the local branch and decides when it's pushed, opened as a PR, and merged
   (after CI passes). Agents only push or merge when the owner asks.
6. **Clean up:** PRs are squash-merged, and GitHub deletes the branch automatically after the merge. The merged
   PR keeps the full record (commits, description, reviews, checks), and its branch can be restored from the PR
   page if ever needed. Then run `scripts\dev\tidy-branches.ps1 -Apply` (without `-Apply` it only shows what it
   would do): it deletes local branches and agent worktrees whose PR merged, never anything unpushed, and moves
   any branches stacked on them onto the new `main`.

### Branches: independent first, stack only when needed
- A feature that doesn't need unmerged work branches from `main`, so it can be reviewed and merged on its own.
- Work that needs an unmerged branch is **stacked** on it. Its PR targets that branch; when the lower PR merges,
  GitHub retargets the next one to `main`. Merge stacks bottom-first.
- The repo sets `rebase.updateRefs`, so one `git rebase` moves a whole stack and every branch label in it
  follows. After the bottom PR is squash-merged, `tidy-branches.ps1` does this for you.

## Rules every agent follows
- Small changes, one purpose each. Commit locally; the owner decides what gets pushed.
- **Never commit real personal/financial data**, keys, tokens, or `.env` files. Test data is fake.
- Money is integer cents. Dates are ISO `YYYY-MM-DD`.
- Small files, no repetition ([CONVENTIONS.md](CONVENTIONS.md)): one job per file, shared helpers instead of copies,
  one topic per doc.
- Every PR explains *what* and *why* in words a non-programmer can follow.
- Big decisions get an ADR in `docs/adr/` (one page: context, decision, consequences).

## Using the agents yourself
In Claude Code, from this folder, ask for an agent by name, e.g.:

> "Use the finance-tax-expert agent to add support for HSA contributions."

> "Have the security-reviewer agent review PR #12."
