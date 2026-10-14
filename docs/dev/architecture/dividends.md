# Dividends from your transactions (roadmap #12e)

Code: `services/investing/dividend_matching.py` (find dividends, file them, link sweeps), `services/investing/dividends.py` (yearly
list, "not a dividend"), `services/budget/named_categories.py` (the "Dividends" category, shared with gift categories),
`schemas/investing/dividends.py`, `routers/investing/dividends.py`. Estimates, not tax advice. User guide:
[docs/guide/dividends.md](../../guide/dividends.md).

## Routes (this computer, or a joined one)

- `GET /api/local/dividends/{tax_year}`: dividends paid that year (by transaction date), oldest first, each with
  its payer, account, amount, `taxed` (false in a retirement account or HSA, `TAX_FREE_KINDS`) and
  `sweep_transaction_id`; plus `total_cents` and `taxed_cents`.
- `POST /api/local/dividends/find`: look through every transaction (for data imported before this existed).
- `POST /api/local/dividends/{id}/dismiss`: not a dividend. Kept with `dismissed = true` so it's never found again;
  its sweep is freed, and the payment leaves "Dividends" if Budget Buddy put it there.
- `GET /api/local/transactions?hide_dividends=true` leaves out dividends and their linked sweeps.
- Bank CSV import results gain `dividends_found` and `dividend_sweeps_linked`.

## Table

`dividends` (migration 0019): `transaction_id` (unique, `ON DELETE CASCADE`), `sweep_transaction_id` (indexed,
shared by several when one sweep covers them, migration 0026; `ON DELETE SET NULL`), `sweep_by_hand` (0027: you linked it, see [bank-trades.md](bank-trades.md#routes-under-stocks-so-joined-computers-and-phones-see-them-too)), `payer` (from the description), `dismissed`. The date, amount and account are the
transaction's, never copied.

## Rules

- **When**: after a bank file is imported (before transfer matching), after a transaction is added by hand, and on
  `find`.
- **A dividend** is a regular (`normal`) money-in transaction, not a transfer, paycheck deposit or donation, whose
  description has the whole word dividend(s), or div(s) in a brokerage, retirement or HSA account, and none of
  "non-dividend", "return of capital", "exempt", "div of", "division" or "payroll". It goes in the income category
  "Dividends" (made the first time; `category_source` stays null, as for transfers) unless you or a rule already
  set its category, or "Dividends" names one of your non-income categories.
- **Budget**: in a retirement account or HSA (`TAX_FREE_KINDS`), a dividend and its linked sweep are left out of
  the monthly summary (`transaction_roles.dividends_kept_inside`), so they're neither income nor saved; the budget engine and
  trend use the same summary. Elsewhere a dividend is income and its sweep is always left out, even with a category (it
  only parks the cash; "needs a category" doesn't list it either), the same as a trade's sweep.
- **Totals** only count dividends whose payment is still money in and `normal`. Two `find` runs at once: the
  second adds nothing (a savepoint catches the unique-constraint clash).
- A linked sweep doesn't show under "needs a category" (it only parks the cash). Stock trades and their sweeps
  work the same way ([bank-trades.md](bank-trades.md)).
- **Its sweep** is a regular money-out transaction in the same account, for exactly the same amount, from 1 day
  before to 3 days after, with the word "sweep" in it. Closest date wins, then the one added first. One sweep can
  also cover several dividends and trades whose amounts add up to it ([bank-trades.md](bank-trades.md)). Sweeps keep their own category (kept, but never counted), and a linked sweep is never matched as a transfer.
- **Payer**: the description up to "common stock", "cash div", "qualified/ordinary dividend", "dividend" or "div".
- Not handled yet: qualified vs ordinary (only the 1099-DIV knows), foreign tax paid, reversals (dismiss the
  dividend by hand), interest from sweep or money-market funds, January payments of dividends declared in the
  last quarter (the 1099-DIV counts them in the year before), and dividends on the tax summary page.
