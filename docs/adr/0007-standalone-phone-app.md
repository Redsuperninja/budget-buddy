# ADR-0007: A fuller phone app that can work on its own

**Status:** Accepted, 2026-10-07 (the owner approved the two-step plan).

## Context
Today the phone is a companion ([ADR-0002](0002-wifi-qr-sync.md), [ADR-0004](0004-sync-contract-v1.md)): it
shows a read-only snapshot from the Home Base and uploads receipts, and it only syncs on home Wi-Fi. The owner
wants a more fully featured phone app, possibly one that works **without** a computer. That changes where the
data lives and which device is "in charge" of it.

Two shapes:
1. **Companion+ (phone edits, Home Base stays in charge).** The phone can add and edit transactions, categorize,
   change budgets and run the suggested budget offline, then sends the changes on the next sync. Needs a change
   log and conflict rules in the sync contract (v2).
2. **Standalone (phone can be the only device).** The phone has its own encrypted database and runs the budget
   and tax logic itself. A Home Base becomes optional: pair one later and the two sync both ways.

## Decision
- **Do it in steps.** First Companion+ (shape 1), then Standalone (shape 2) on top of the same pieces, so each
  step ships something usable.
- **Phone storage:** an on-device SQLite database (Expo SQLite), encrypted with a key kept in the phone's secure
  storage. Money stays integer cents and dates ISO, the same as the server.
- **Sync contract v2:** each change gets an ID and a time; the Home Base applies them in order. For two edits of
  the same thing, the most recent wins and the other is shown to the user, never silently dropped. Contract v1
  keeps working for older phones until v2 is in both apps.
- **Shared rules, two copies:** budget math (summary, percentages, 50/30/20 suggestion, savings transfers) is
  needed on both sides. Following the "parts never import each other" rule, the phone keeps a TypeScript copy,
  and both copies are checked against **shared test vectors** (JSON inputs and expected outputs in `docs/api/`),
  as the sync envelope already is.
- **Standalone features in priority order:** manual transactions and categories; budgets and the monthly
  summary; receipts with the camera; CSV import from a file; bank connections only through a Home Base at first
  (ADR-0006 keeps the credential off the phone); tax summary last.
- **Still local-first:** no cloud account and no Budget Buddy server on the internet. Backup is an encrypted
  file the user saves (roadmap #24), on the phone as well.

## Consequences
- The biggest change since the start: sync becomes two-way, and budget logic exists in two languages.
- Needs `architect` (contract v2), `security-reviewer` (phone database, keys, backup) and `finance-tax-expert`
  (shared vectors) at each step.
- Expo Go may not be enough for an encrypted database; a development build (EAS) may be needed, which changes
  the tester setup.
- Getting it into app stores (accounts, review, privacy labels) is part of public release prep (#25).
