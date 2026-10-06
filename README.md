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

## How it's organized

```
budget-buddy/
├── server/        Home Base: Python (FastAPI) + SQLite, runs on your PC
├── mobile/        Phone app: Expo (React Native), iPhone + Android
├── docs/          Architecture, decisions (ADRs), user guides, workflow
├── scripts/       Setup, testing and demo-data helpers (see docs/TESTING.md)
└── .claude/agents Specialized AI agents that build & maintain this project
```

- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Roadmap and what's next: [docs/ROADMAP.md](docs/ROADMAP.md)
- Try it out (early preview, demo data only): [docs/TESTING.md](docs/TESTING.md)
- How the project is built and managed (agents, PRs): [docs/WORKFLOW.md](docs/WORKFLOW.md)

## Status

Early development. See the roadmap for what's done and what's next.

## Built with Claude

The code in Budget Buddy is built by [Claude Code](https://claude.com/claude-code), Anthropic's AI coding assistant.
The design and every review are done by the project's owner, a human who decides what gets built and approves
each change before it's merged. See [docs/WORKFLOW.md](docs/WORKFLOW.md) for how Claude's specialized agents
split the work.

## License

MIT, see [LICENSE](LICENSE).
