# Stocks: lots, sales, and gains (roadmap #12)

Code: `services/stock_records.py` (converters, filters, account checks, re-matching), `services/stock_lots.py`,
`services/stock_sales.py` (sales and the yearly gains summary), `services/stock_gains.py` (pure math, no
database), `routers/stocks.py`. Estimates, not tax advice. User guide:
[docs/guide/stocks.md](../../guide/stocks.md).

## Routes (this computer only)

- `GET/POST /api/local/stocks/lots`, `GET/DELETE /api/local/stocks/lots/{id}`: shares bought. Send the symbol,
  `acquired_on`, the shares as text (`"shares": "2.5"`) or `shares_micro`, and the total paid including fees
  (`cost_basis` dollar text or `cost_basis_cents`). Each purchase shows shares left and `long_term_from`.
  Filters: `symbol`, `account_id`.
- `GET/POST /api/local/stocks/sales`, `GET/DELETE /api/local/stocks/sales/{id}`: shares sold, with the total
  received after fees (`proceeds` or `proceeds_cents`). Each sale lists the purchases it used (oldest first),
  with cost, gain or loss, term, and a possible-wash-sale flag. Filters: `symbol`, `account_id`, `tax_year`.
  Newest first.
- `GET /api/local/stocks/gains/{tax_year}`: short- and long-term totals for sales in that year.
- Importing purchases and sales from a CSV file: [stock-import.md](stock-import.md).

## Tables

`stock_lots` = one purchase. `stock_sale_orders` = one sale as entered (symbol, date, shares, proceeds after
fees, optional account). `stock_sales` = the part of an order that came out of one lot (`order_id`, `lot_id`,
shares, that lot's share of the proceeds); deleting an order deletes its parts (`ON DELETE CASCADE`). Migration
0007 added `stock_sale_orders` and `stock_sales.order_id` ([database.md](database.md)).

## Rules

- **Shares** are whole millionths of a share (`shares_micro`, `SHARES_SCALE = 1_000_000`), never floats. The API
  also takes and returns them as text (`"2.5"`).
- **FIFO, rebuilt.** Each symbol + account is matched on its own, oldest purchase first (same date: the one
  entered first), using only purchases dated on or before the sale. That symbol + account's `stock_sales` rows
  are rebuilt on every add or delete, so a purchase entered late still sells first.
- Selling more than was held is refused (422 `not_enough_shares`); deleting a purchase a sale needs is refused
  (409 `purchase_in_use`). There's no edit: delete and re-enter.
- **Calculated, not stored** (`stock_gains.py`): cost basis per part, gain, term, wash-sale flag, yearly totals.
  - Rounding: a lot's cost is shared out over its sold shares cumulatively, rounding half up, so a fully sold
    lot's parts add up to exactly its cost. A sale's proceeds are split over its lots the same way.
  - Term: the holding period starts the day after purchase. Long term = sold on or after the day one full year
    from that start has passed (`long_term_from`); a year starting Feb 29 ends Feb 28.
  - Possible wash sale (flag only, nothing adjusted): a loss part, with another purchase of the same symbol in
    any account entered here within 30 days before or after the sale. The rest of the losing lot doesn't count
    (Rev. Rul. 56-602); another lot the same sale used up completely doesn't count; one it only partly used
    does. IRA/HSA and spouse purchases aren't known, so they aren't checked.
  - Year: a sale counts in the year of its sale date.
- **Statutory constants** (one year, 30 days) live in `stock_gains.py` with sources, not in the per-year tax data
  files: they don't change by year.
- **Accounts.** Any account can hold purchases and sales. Sales in a retirement account or HSA (`TAX_FREE_KINDS`)
  aren't taxed: `SaleOut.taxed` is false, they have no wash-sale flag, and the gains summary leaves them out.
  Purchases there still count when checking someone else's loss for a possible wash sale (any account entered
  here). An account's kind can change at any time (the summary follows the current kind); an account with
  stock records can't be deleted.
- **Holdings and prices** are on [investments.md](investments.md).
- Every result is labeled an estimate, not tax advice.
