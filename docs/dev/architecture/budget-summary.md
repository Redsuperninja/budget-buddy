# Categories and the monthly summary

Code: `services/categories.py`, `services/summary.py` and their routers. Transaction kinds and signs:
[ledger.md](ledger.md).

## Routes (this computer only)

- `GET/POST /api/local/categories`, `GET/PATCH /api/local/categories/{id}`.
- `GET /api/local/summary/monthly?month=YYYY-MM`: income, spending and savings for that month.

## Categories

- A category has a name (unique, ignoring upper/lower case), a group (`needs`, `wants`, `savings`,
  `income`, or the built-in `transfer`), and a `budget_cents` target (not negative). You can rename it and
  change its budget. The group can't change, and new categories can't use the `transfer` group.
- **Budgets apply to every month.** There is no per-month budget, so changing one also changes what past
  months show.
- Default categories are seeded by migration 0002.

## Monthly summary rules

- The summary only counts `normal` and `refund` transactions, by their own date, from the first to the last
  day of the month. **Transfers and adjustments (including opening balances) are never counted.**
- The category's group decides where a transaction goes: `income` is income; `needs` and `wants` add up to
  `spending_cents`; `savings` is `saved_cents`. Spending and savings are shown as money out, positive.
  **Refunds lower spending** (or savings) in their category and are never income. Spending can go
  negative if refunds are bigger than spending.
- Transactions with no category, and refunds filed under an income or transfer category, can't be placed.
  They are not guessed at: they show up as `unassigned_in_cents`, `unassigned_out_cents` (both positive)
  and `unassigned_count`, and are left out of the totals.
- Paychecks never add income by themselves ([paychecks.md](paychecks.md)).
- **Known gap:** money moved into your own savings account is a transfer, so it isn't counted as saved yet.
  Roadmap item 10b covers this.

The phone's snapshot reuses this summary (sync contract §5).
