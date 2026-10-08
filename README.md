# Budget Buddy

A private, local-first budgeting and tax-prep helper.

- **Home Base** (runs on your computer): stores your checking, savings, paychecks,
  receipts, stock sales and donations in an encrypted database that never leaves your house.
- **Phone app** (iPhone & Android): snap receipts as you go and see your budget breakdown.
  Every 1–3 days it reminds you to **sync**: be on home Wi-Fi, open the app, tap **Sync**. That's it.

> Budget Buddy organizes your records and estimates numbers to help you prepare.
> It is not tax advice. Check important decisions with a tax professional.

## What it does

| Area | Features |
| --- | --- |
| Money in | Paychecks (gross, taxes withheld, net, 401k/HSA) |
| Accounts | Checking & savings — import bank CSV exports or enter manually |
| Spending | Receipts (photo + amount + category), auto-categorized transactions |
| Budget | Suggested budget from your real income & spending, monthly targets vs. actual |
| Taxes | Charitable donations, stock purchases and sales (oldest shares first, short/long-term gains, possible wash-sale flags), other deductions, year-end summary export |

## Quick start

**On your computer:**

1. Set up Home Base (the Python server): from the `server/` folder, run `python -m venv .venv` and `.venv\Scripts\pip install -e ".[dev]"` (Windows) or use `.venv/bin/...` on macOS/Linux.
2. Start it: `.venv\Scripts\python -m app` (Windows) or `.venv/bin/python -m app` (macOS/Linux).
3. Open the dashboard in your browser: <http://127.0.0.1:8765/>.
4. Add accounts, transactions, and connect your phone.

Step-by-step help for everything: [the user guide](docs/guide/README.md).

## How it's organized

```
budget-buddy/
├── server/        Home Base: Python (FastAPI) + SQLite, runs on your PC
├── dashboard/     Web page for the computer: plain HTML/CSS/JS, talks to the Home Base over HTTP
├── mobile/        Phone app: Expo (React Native), iPhone + Android
├── docs/          User guides (guide/), developer docs (dev/), sync contract, decisions (ADRs), roadmap
├── scripts/       Setup, testing and demo-data helpers (see scripts/README.md)
└── .claude/agents Specialized AI agents that build & maintain this project
```

- All the docs at a glance: [docs/README.md](docs/README.md)
- How it's built (for developers): [docs/dev/README.md](docs/dev/README.md)
- Roadmap and what's next: [docs/ROADMAP.md](docs/ROADMAP.md)
- Try it out (early preview, demo data only): [docs/guide/set-up-for-testing.md](docs/guide/set-up-for-testing.md)
- How the project is built and managed (agents, PRs): [docs/dev/workflow.md](docs/dev/workflow.md)

## Status

Early development. See the roadmap for what's done and what's next.

## Built with Claude

The code in Budget Buddy is built by [Claude Code](https://claude.com/claude-code), Anthropic's AI coding assistant.
The design and every review are done by the project's owner, a human who decides what gets built and approves
each change before it's merged. See [docs/dev/workflow.md](docs/dev/workflow.md) for how Claude's specialized agents
split the work.

## License

MIT, see [LICENSE](LICENSE).
