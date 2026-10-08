# Working on Budget Buddy

Start page for developers and AI agents. Read only what your task needs.

## Read in this order

1. [architecture/README.md](architecture/README.md): the parts, their boundaries, principles, and the topic list.
2. [../ROADMAP.md](../ROADMAP.md): what's done and what's next.
3. [../adr/](../adr/): decisions and why they were made.
4. [workflow.md](workflow.md) and [conventions.md](conventions.md): how changes are made, and the file rules.
5. The README of the part you're changing: [server](../../server/README.md), [dashboard](../../dashboard/README.md),
   [mobile](../../mobile/README.md), [scripts](../../scripts/README.md).

## Where each fact lives

| Fact | Only here |
| --- | --- |
| How a feature works (rules, routes, tables) | `architecture/<topic>.md` |
| Phone ↔ computer wire format | [../api/sync-contract.md](../api/sync-contract.md) and its section files |
| Environment variables | [settings.md](settings.md) |
| How to run tests, and CI | [testing.md](testing.md) |
| Tax-year numbers | `server/app/tax_data/<year>.json`, explained in [tax-data.md](tax-data.md) |
| How to run, check and lay out one part | That part's README |
| What a person sees and does | [../guide/](../guide/) |

When you change code, update the matching `architecture/<topic>.md` and the part's README in the same branch.
