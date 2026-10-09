# Dividends

> **Estimates, not tax advice.** Check your dividends against the Form 1099-DIV from your broker.

When you import a bank or brokerage file (or add a transaction by hand), Budget Buddy spots dividends, like
`FAKECO INC COMMON STOCK CASH DIV ON 1 SHS REC 08/25/26 PAY 09/08/26`, and:

- puts them in the **Dividends** income category (unless you already picked a category for that payment);
- finds the **deposit sweep** that moved the same cash on, like `IRA DEPOSIT SWEEP ... INTRA-DAY DEPOSIT`: money
  out of the same account, for the same amount, within a few days. The sweep keeps its own category;
- keeps a dividend record, listed by year on the **Stocks** page (under **Taxes**).

## See your dividends

Go to **Taxes**, then **Stocks**, and look at **Dividends in** the year you picked. Each row shows the date, who
paid it, the account, the amount, whether it's taxed, and whether its deposit sweep was found. Dividends inside a
retirement account (like an IRA or 401(k)) or an HSA aren't taxed, so they're left out of the taxed total.

Imported your files before this was added? Click **Find dividends** once to look through everything.

## Hide them from your transactions

Dividends and their sweeps can crowd the **Transactions** list. Tick **Hide dividends and sweeps** to leave them
out. Untick it to see them again.

## Something went wrong?

- **Something that isn't a dividend is listed**: click **Not a dividend** in its row. It won't be picked up again,
  and if Budget Buddy put it in Dividends, it goes back to having no category.
- **The sweep wasn't found**: the sweep must be in the same account, for exactly the same amount, between the day
  before and 3 days after the dividend, and say "sweep". If it came in a later file, click **Find dividends** after
  importing it.
- **Qualified dividends**: Budget Buddy can't tell which dividends are qualified (usually taxed at a lower rate).
  Your Form 1099-DIV says.
