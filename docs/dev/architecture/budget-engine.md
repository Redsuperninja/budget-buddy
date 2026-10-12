# Suggested budget (budget engine)

Code: `services/budget/budget_engine.py`, routes in `routers/budget/budget_plan.py`. Roadmap item 10. Builds on the
[monthly summary](budget-summary.md) and its percentage budgets.

## Routes (this computer only)

- `GET /api/local/budget/suggestion?month=YYYY-MM` (this month when left out): the plan for that month, from
  the 3 full months before it. Read-only.
- `POST /api/local/budget/suggestion/apply` with `{"month": "YYYY-MM", "use": "amounts" | "percentages"}`:
  saves the suggestion as the budget of every needs, wants and savings category. Income categories are not
  touched. `409 no_income` when there's no income to plan with. As percentages, a suggestion that rounds to
  0.00% becomes a $0 amount budget (a percentage budget must be above zero). As percentages without a planned
  income, the average income is saved as the planned income first (returned as `planned_income_cents`), so
  the percentages don't start at $0 each month before pay arrives.

## How the plan is built

The 50/30/20 guide (needs, wants, savings) is a rule of thumb, not tax data, so its percentages are a constant
in the engine (`GUIDE_BP`).

- **Averages:** the monthly summary for each of the 3 months before; months with no activity at all are left
  out of the average (so a new user isn't diluted by empty months). Savings averages include transfers into
  savings (10b) at group level.
- **Income `I`:** the planned monthly income when set, otherwise the average income.
- **Needs** keep their average (bills can't be cut by a budget).
- **Savings** aim for 20% of `I`, or the current saving rate if that's higher.
- **Wants** get what's left, up to 30% of `I`; anything left over goes to savings, so the plan uses all of `I`.
  When needs plus the savings goal are more than `I`, wants get 0 and savings get `I - needs` (never below 0).
- Inside wants and savings the group amount is shared by each category's average (even split when the group
  has no history), in whole cents that add up exactly (largest remainder, `split()`). Savings also share with
  the average money moved into savings accounts (10b), which has no category: that part is
  `savings_by_transfer_cents` (all of it when there are no savings categories; `split_savings()`).
- Averages are whole cents rounded down. A note says when needs alone are as much as the income or more.

The response has per-group and per-category `average_cents`, `suggested_cents` and `suggested_percent_bp`
(share of `I`), the category's current budget, `months_with_data`, and plain-English `notes` (short history,
no income, needs over half, needs leaving under 20% for savings, already saving more than 20%).
