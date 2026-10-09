# Categories and the monthly summary

Code: `services/categories.py`, `services/summary.py` and their routers. Transaction kinds and signs:
[ledger.md](ledger.md).

## Routes (this computer only)

- `GET/POST /api/local/categories`, `GET/PATCH /api/local/categories/{id}`.
- `GET /api/local/summary/monthly?month=YYYY-MM`: income, spending and savings for that month.
- `GET /api/local/summary/trend?end=YYYY-MM&months=N` (1 to 24, default 12): income, spending and saved for each
  month up to and including `end`, oldest first, by the same rules (`services/trend.py`). Used by the charts.
- `GET/PUT /api/local/budget/plan`: `{"planned_income_cents": int | null}`, the planned monthly income that
  percentage budgets are shares of (one row in `budget_plan`).

## Categories

- A category has a name (unique, ignoring upper/lower case), a group (`needs`, `wants`, `savings`,
  `income`, or the built-in `transfer`), and a `budget_cents` target (not negative). You can rename it and
  change its budget. The group can't change, and new categories can't use the `transfer` group.
- **Percentage budgets:** instead of `budget_cents`, a category can have `budget_percent_bp`, a share of monthly
  income in basis points (1 to 10,000; `1500` = 15%). Sending `budget_cents` switches a category back to an
  amount (the percentage is cleared); sending a percentage sets `budget_cents` to 0. Both at once is a 422.
- **Income has no budget**: it's what the other budgets are measured against. A nonzero `budget_cents` or any
  percentage on an income category is a 422 ("Income categories don't have a budget"), and one saved by an older
  version is ignored (`budget_plan.budget_for` returns 0), so the income group's budget is always 0. Math helpers: `app/percent.py` (whole numbers, halves rounded away
  from zero).
- **Budgets apply to every month.** There is no per-month budget, so changing one also changes what past
  months show.
- Default categories are seeded by migration 0002.

## Monthly summary rules

- The summary only counts `normal` and `refund` transactions, by their own date, from the first to the last
  day of the month. **Transfers and adjustments (including opening balances) are never counted.**
  Neither are dividends paid inside a retirement account or HSA, or their deposit sweeps
  ([dividends.md](dividends.md)), or transactions classified as stock trades ([stocks.md](stocks.md)).
- The category's group decides where a transaction goes: `income` is income; `needs` and `wants` add up to
  `spending_cents`; `savings` is `saved_cents`. Spending and savings are shown as money out, positive.
  **Refunds lower spending** (or savings) in their category and are never income. Spending can go
  negative if refunds are bigger than spending.
- Transactions with no category, and refunds filed under an income or transfer category, can't be placed.
  They are not guessed at: they show up as `unassigned_in_cents`, `unassigned_out_cents` (both positive)
  and `unassigned_count`, and are left out of the totals.
- **Budget income:** a percentage budget's `budget_cents` in the summary is its share of the month's budget
  income: the planned income when one is saved, otherwise that month's actual income (never below zero). The
  summary reports it as `budget_income_cents` and `budget_income_source` (`planned` or `actual`). Without a
  plan, a percentage budget grows as the month's pay comes in.
- **Shares of income:** each needs, wants and savings group has `percent_of_income_bp`, its actual as a share
  of the month's actual income (`null` for the income group or when no income came in). This is the 50/30/20
  check.
- Paychecks never add income by themselves ([paychecks.md](paychecks.md)).
- **Transfers into savings count as saved** (roadmap 10b, `services/savings_transfers.py`): a linked transfer
  from an everyday account into a `savings`, `brokerage`, `retirement` or `hsa` account adds to `saved_cents`
  and the savings group's actual; a transfer back out lowers it. Moves between two of those kinds, and
  payments to cards and loans, don't count. The amount is also reported as `saved_by_transfer_cents`. It
  belongs to no category, so the savings group can be more than its categories add up to. Transfers are
  still never income or spending.

The phone's snapshot reuses this summary (sync contract §5), so it gets percentage budgets already worked
out into cents; the wire format didn't change.
