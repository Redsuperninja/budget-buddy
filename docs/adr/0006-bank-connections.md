# ADR-0006: Optional bank connections (live balances and transactions)

**Status:** Proposed, 2026-10-07. Needs the owner's decision before any code.

## Context
The owner wants live checking, savings and investment data from banks such as Chase and Wells Fargo, instead of
only downloading CSV files. Banks don't offer this to individuals directly: most big banks have dropped or limited
the old direct-download (OFX) connections, and new US open-banking rules are still being phased in. In practice
an app connects through an **aggregator**, a company that holds the bank login or OAuth grant and passes the data
on. That means data leaves the computer and goes through a third party, which is a change to the local-first
promise in [ADR-0001](0001-local-first-stack.md).

Options looked at (prices and terms change; check before deciding):

| Option | How it works for us | Cost | Chase / Wells Fargo | Fit |
| --- | --- | --- | --- | --- |
| **SimpleFIN Bridge** | The user signs up with SimpleFIN, links banks there, and pastes a one-time setup token into Budget Buddy. We get read-only accounts, balances and transactions over HTTPS. No developer account or company review. | About $15/year, paid by the user to SimpleFIN | Listed by apps that use it; confirm in the SimpleFIN app before paying | Best fit: one token per user, read-only, no app-wide secret in our code |
| **Plaid** | We register as a developer company. Bank login runs in Plaid Link; we hold an app-wide client ID and secret. Chase and Wells Fargo need OAuth, which needs Production or Trial access, a company profile and a security questionnaire. | Free Trial up to about 10 connected banks for new teams; pay-as-you-go after | Yes, after approval | Heavier: a secret every install would need, company review, redirect URIs |
| Teller, MX, Finicity and others | Similar to Plaid: developer contracts | Varies | Varies | Same issues as Plaid |
| Direct OFX | Talk to the bank ourselves | Free | Mostly no longer offered | Not workable |
| CSV import (today) | The user downloads a file | Free | Yes | Stays as the always-available option |

## Decision (proposed)
- **Opt-in only.** Bank connections are off by default. CSV import stays, and the app works fully without them.
  Turning it on shows a plain-English screen: which company sees the data, what it costs, how to turn it off.
- **Start with SimpleFIN Bridge** behind a small "bank source" interface, so Plaid (or the US open-banking rule)
  can be added later without touching the rest.
- **Read-only.** We only read accounts, balances, transactions and (where offered) investment holdings. Nothing
  can move money.
- **Security:** the SimpleFIN access URL is a credential. It is stored encrypted like other secrets
  ([ADR-0003](0003-encryption-at-rest.md)), never logged, never synced to the phone. Only the Home Base talks to
  the aggregator, only over HTTPS to its fixed address. Removing the connection deletes the stored credential.
- **Data flow:** fetched transactions go through the same path as CSV rows: deduplicated (by the aggregator's
  transaction ID, then the CSV fingerprint rules), auto-sorted by the rules (#9), never changing what the user
  edited. Balances are shown as "from your bank, as of <time>". Fetching runs when the user clicks "Update from
  bank" and, if they choose, once or twice a day while the Home Base is running.
- **Investments:** balances first; holdings and lots only if the aggregator provides them reliably, and never
  replacing the user's own cost-basis records (#12) without asking.

## Consequences
- ADR-0001's "no third-party calls with user data" becomes "none unless the user turns on a bank connection".
  The README, guide and security docs must say so plainly.
- Needs `security-reviewer` on every part (credential storage, outbound HTTPS, parsing).
- Adds a cost the user pays to a third party, and a dependency that can break when banks change.
- Plaid stays possible later, but it needs a company account and a secret that can't ship inside an open-source
  app, so it would likely need a small hosted relay. That is a separate decision.

## Sources (checked 2026-10-07)
- SimpleFIN Bridge: <https://beta-bridge.simplefin.org/>, Actual Budget's setup guide
  <https://actualbudget.org/docs/advanced/bank-sync/simplefin/>
- Plaid: pricing <https://plaid.com/pricing/>, free use
  <https://support.plaid.com/hc/en-us/articles/16194695660311-Can-I-use-Plaid-for-free>, OAuth guide
  <https://plaid.com/docs/link/oauth/>, launch checklist <https://plaid.com/docs/launch-checklist/>
