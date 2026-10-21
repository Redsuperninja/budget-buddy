# ADR-0015: First-start setup: one skippable page, progress kept by the Home Base

**Status:** Accepted by the owner, 2026-10-20 (roadmap 25e to 25h): a skippable Setup page, and the recovery
phrase step is an "I've written it down" tick.

## Context
A brand-new user today opens Home and sees the **Get started** checklist (accounts, transactions, budgets, optional
phone; `dashboard/js/screens/home/home-start.js`). Everything else happens silently or not at all:
- The master key is made on first start (`crypto/keys.py` `load_or_create_master_key`) and the **recovery phrase**
  is shown only if they find Devices → Backups → "Show my recovery phrase" (24c). READ ME FIRST tells them to write
  down "the recovery phrase Budget Buddy shows you", but nothing shows it unasked.
- Someone moving to a new computer has no hint that they can **restore a backup** instead of starting over.
- Nothing asks them to **make a backup**, and the Home Base doesn't remember when the last one was made.
- The starter categories (migration 0002 and later ones such as 0018's "Other Expenses") are generic with $0 budgets; nobody
  is asked which ones they need or what they take home a month (`budget_plans.planned_income_cents`).
- No **filing status** or **state** is stored anywhere; the tax summary shows all four filing statuses and has no
  state tax data at all.

Progress kept in `localStorage` would differ between the desktop window and a browser on the same computer.

## Decision (proposed)
1. **A Setup page, not a modal wizard.** `#setup` opens instead of Home on this computer while setup isn't
   finished and there are no accounts or transactions. Steps, each skippable, each one sentence:
   **Start fresh or restore a backup** (restore reuses Devices → Backups) → **Save your recovery phrase** (reuses
   `phraseCard`, then "I've written it down") → **Your first account** (add one, or import a bank file) →
   **Starter budget** (untick categories you don't need; optional monthly take-home pay) → **Phone, optional**
   (the browser way, ADR-0009). "Finish later" goes to Home; the Get started checklist carries what's left.
2. **The Home Base keeps the progress** in one new row (`setup_progress`): `finished_at`, `phrase_saved_at`,
   `last_backup_at`. `last_backup_at` is set by the server when it makes a backup file (dashboard or command
   line), never by the browser. Dates only: no phrase, key or file contents. Routes are this-computer-only, like
   Backups.
3. **Not asked in 0.1:** filing status (nothing uses it yet; the tax summary keeps showing every status) and state
   (no state tax support; the README says so). Each is added only with a feature that uses it.
4. **Get started and Home** gain "Save your recovery phrase" and "Make a backup" steps, and Home's "needs you" list
   reminds about a backup older than 30 days.

## Consequences
- A stranger is led through the two things that can't be fixed later (phrase, backup) before typing any data.
- One small migration and two routes; existing users see no Setup page (they already have accounts) but do get
  the new checklist steps.
- "I've written it down" is trust, not proof. Retyping chosen words would prove it but sends words to the server
  and adds a form to secure; left out unless the owner wants it.
- Tests: the Setup page's step logic is pure and unit-tested; the server tests cover the routes, that they refuse
  other computers, and that `last_backup_at` changes only when a backup file is written.
