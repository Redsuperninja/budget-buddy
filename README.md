# Budget Buddy

A private, local-first budgeting and tax-prep helper. Your money records stay on your own computer, encrypted,
with no cloud, no account and no bank passwords.

![Budget Buddy's Home page: money in, spent, saved and left over (demo data)](docs/showcase/images/home.png)

- **Home Base** (runs on your computer): stores your accounts, transactions, paychecks, receipts, stock sales and
  donations in an encrypted database that never leaves your house.
- **Dashboard**: a simple view for everyday use, and **All tools** for people who want full control.
- **On your phone**: open Budget Buddy in your phone's web browser at home, with nothing to install. (A phone app for
  receipt photos and offline viewing is in testing.)

> Budget Buddy organizes your records and estimates numbers to help you prepare.
> It is not tax advice. Check important decisions with a tax professional.

**Showcase:** [What Budget Buddy is (plain English)](docs/showcase/overview.md) ·
[How it works (technical)](docs/showcase/technical.md) · **Privacy:** [what it keeps and where](docs/PRIVACY.md) · **Security:** [report a problem](SECURITY.md)

## What it does

| Area | Features |
| --- | --- |
| Getting started | A **Get started** checklist on Home; a simple view, with **All tools** one switch away in **Settings**; every box folds up, and remembers it |
| Money in | Paychecks (gross, taxes withheld, net, 401k/HSA), started for you from pay deposits in your bank file |
| Accounts | Checking, savings, cards, loans, brokerage, retirement and HSA: import bank CSV exports or enter by hand |
| Spending | Search and filter by category; auto-sorted transactions (rules, and ones learned from your choices), transfers between your accounts linked for you, receipts from the phone app |
| Budget | Suggested 50/30/20 budget from your real income and spending, monthly targets vs. actual, charts, this month against last month, categories grouped by kind |
| Investments | Holdings by account at live prices (optional, Finnhub) or prices you enter; broker activity and positions files; 401(k), IRA and HSA limits |
| Taxes | Donations, stock gains (oldest shares first, short/long-term, possible wash sales), dividends, other deductions, a yearly summary to download or print |
| Devices | Phones and other computers at home join with a one-time code |

## Quick start

**Windows (easiest):** download `Budget-Buddy-<version>-Windows.zip` from the Releases page, unzip it, and
double-click **Install Budget Buddy** ([guide](docs/guide/install.md)). No Python needed.

**From source (Windows, macOS, Linux):** install Python 3.12 or newer, then open the **launch** folder and start
**Start Budget Buddy** (double-click it on Windows; **Start Budget Buddy.command** on a Mac; run
`./launch/start-budget-buddy.sh` on Linux). It sets itself up the first time, starts the Home Base and opens the
dashboard ([guide](docs/guide/start-budget-buddy.md)). On Windows, for the desktop app with a tray icon,
double-click **Build desktop app**, then **Install desktop app** ([guide](docs/guide/desktop-app.md)).

Then follow the **Get started** list on Home. Step-by-step help for everything: [the user guide](docs/guide/README.md).

## How it's organized

```
budget-buddy/
├── server/        Home Base: Python (FastAPI) + SQLite, runs on your PC
├── dashboard/     Web page for the computer: plain HTML/CSS/JS, talks to the Home Base over HTTP
├── mobile/        Phone app: Expo (React Native), iPhone + Android
├── desktop/       Windows app: the dashboard in its own window, and a light tray icon
├── launch/        What you double-click: start, build and install the desktop app (and the built app)
├── docs/          User guides (guide/), showcase, developer docs (dev/), sync contract, decisions (ADRs), roadmap
├── scripts/       What launch/ runs; testing/, release/ and dev/ tools (see scripts/README.md)
├── packaging/     The Windows download: both build recipes, the installer and its read-me (windows/)
└── .claude/agents Specialized AI agents that build & maintain this project
```

- All the docs at a glance: [docs/README.md](docs/README.md)
- How it's built (for developers): [docs/dev/README.md](docs/dev/README.md)
- Roadmap and what's next: [docs/ROADMAP.md](docs/ROADMAP.md)
- Try it out with made-up demo data: [docs/testing/](docs/testing/README.md)
- Make a release (the Windows download): [docs/dev/release.md](docs/dev/release.md)
- How the project is built and managed (agents, PRs): [docs/dev/workflow.md](docs/dev/workflow.md)

## Status

Early release (0.1). Windows download available; phones use the browser for now. See the roadmap for what's
next.

## Built with Claude

The code in Budget Buddy is built by [Claude Code](https://claude.com/claude-code), Anthropic's AI coding assistant.
The design and every review are done by the project's owner, a human who decides what gets built and approves
each change before it's merged. See [docs/dev/workflow.md](docs/dev/workflow.md) for how Claude's specialized agents
split the work.

## License

MIT, see [LICENSE](LICENSE).
