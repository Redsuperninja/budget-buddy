# ADR-0006: Bank data without CSV hunting: free and open source first

**Status:** Accepted in direction, 2026-10-07. The owner wants free and open-source options where possible. The
live-connection provider (step 3) is confirmed by testing with the owner's own accounts before it's built.

## Context
The owner wants live checking, savings and investment data from banks such as Chase and Wells Fargo, and prefers
free and open-source options. What exists today (checked 2026-10-07; this changes, so re-check before each step):

| Option | Free? | Open source? | Chase / Wells Fargo | Notes |
| --- | --- | --- | --- | --- |
| **OFX/QFX file download** (the "Quicken / Money" file on the bank's website) | Yes | Open format, open-source readers | Yes, both offer it | Has account numbers, a unique ID per transaction, the balance, and for brokerages the holdings. Still a download, not live. |
| OFX Direct Connect (the bank's own feed, e.g. through `ofxget`) | Yes | Yes | Chase ended it in 2022; Wells Fargo unconfirmed | Most big banks have dropped it. Not something to build on. |
| US open-banking rule (CFPB §1033) | Was meant to be free | Standard APIs | Largest banks first | Blocked by a court and being rewritten, so no date to plan around. |
| **Teller** (bring your own free developer account) | Free developer tier, about 100 live connections | No | Check their list with your own login | Read-only API; the user signs up and puts their own keys and certificate in Budget Buddy, so no secret ships in our code. |
| Plaid (bring your own free account) | Free Trial, about 10 banks, for new teams | No | Yes, OAuth after a short review | Heavier setup (company profile, redirect address). |
| SimpleFIN Bridge | No, about $15/year | Open protocol, paid service | Listed by apps that use it | Easiest setup; kept as a paid choice. |
| Screen-scraping your bank login | Free | Some tools exist | Fragile | Against bank terms, and means storing your bank password. Rejected. |

## Decision
1. **Free and open, now: bank-file import (OFX/QFX).** Budget Buddy reads the bank's OFX/QFX download as well as
   CSV: no column guessing, duplicates spotted by the bank's own transaction ID, the statement balance recorded,
   and for brokerage files the holdings shown next to the user's own lots (never replacing their cost basis
   without asking). The parser is our own small module, or a library whose license fits our MIT license.
2. **Free and open, next: auto-import folder.** The user picks a folder, for example Downloads. Budget Buddy
   imports new bank files that appear there, for accounts it already knows, and says what it did. Getting fresh
   data becomes "download, done".
3. **Free but not open: optional live connection, bring your own developer key.** Off by default. The user makes
   their own free Teller account (or Plaid, if Teller doesn't cover their banks) and enters their keys. Budget
   Buddy then fetches balances and transactions when asked, and optionally once a day. Behind a small "bank
   source" interface, so §1033 bank APIs or SimpleFIN can be added later.
4. **Always:** CSV import stays; everything is read-only; nothing can move money; bank logins are never stored.

**Security** for step 3: keys and certificates are credentials, stored encrypted ([ADR-0003](0003-encryption-at-rest.md)),
never logged, never synced to the phone. Only the Home Base calls the provider, over HTTPS to its fixed address.
Turning the connection off deletes them. Fetched data takes the same path as imported files (dedupe, auto-sort
rules, never changing what the user edited).

## Consequences
- Steps 1 and 2 keep the local-only promise of [ADR-0001](0001-local-first-stack.md) exactly.
- Step 3 changes ADR-0001's "no third-party calls with user data" to "none unless the user turns on a bank
  connection". The README, guides and security docs must say so plainly, with what the provider can see.
- Every step needs a `security-reviewer` pass (file parsing, folder access, credentials, outbound HTTPS).
- Free tiers have limits and can change. Bring-your-own-key keeps each user inside their own free allowance.

## Sources (checked 2026-10-07)
- OFX: Chase Direct Connect ended <https://infinitekind.tenderapp.com/kb/popular-banks/connecting-to-chase>;
  GnuCash notes on Direct Connect <https://wiki.gnucash.org/wiki/OFX_Direct_Connect_Bank_Settings>;
  ofxtools <https://github.com/csingley/ofxtools>
- §1033 status: <https://openbankingtracker.com/guides/section-1033-status>,
  <https://www.cozen.com/news-resources/publications/2026/section-1033-compliance-date-open-banking-rule-enjoined-and-under-reconsideration>
- Teller: <https://teller.io/>, <https://teller.io/docs/api>; free options overview
  <https://www.openbankingtracker.com/guides/free-open-banking-apis>
- Plaid: <https://support.plaid.com/hc/en-us/articles/16194695660311-Can-I-use-Plaid-for-free>,
  <https://plaid.com/docs/link/oauth/>
- SimpleFIN Bridge: <https://beta-bridge.simplefin.org/>
