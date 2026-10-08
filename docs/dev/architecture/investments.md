# Investments: holdings, prices, retirement limits

Code: `services/stock_holdings.py`, `services/retirement.py`, `routers/stocks.py` (holdings, prices),
`routers/retirement.py`, table `stock_prices` (migration 0015). Dashboard: `screens/investments.js` (Money,
Investments). User guide: [docs/guide/investments.md](../../guide/investments.md). Estimates, not tax advice.

## Holdings

- `GET /api/local/stocks/holdings`: per account (or "Not in an account"), each symbol still held: shares, the cost
  of the shares still held, the latest price, value and the gain or loss not yet sold; totals per account and
  overall (`value_cents` is null while any holding has no price). `taxed` is false for retirement accounts and HSAs.
- Remaining cost of a purchase = its cost minus `share_of(cost, sold, shares)`, the same half-up cumulative rounding
  as the gains ([stocks.md](stocks.md)), so cost held + cost sold is exactly the cost paid.
- Value = `share_of(price_cents, shares_micro, SHARES_SCALE)`: shares times the per-share price, half up to a cent.

## Prices

`POST /api/local/stocks/prices` `{symbol, price_cents | price, as_of}` saves the latest price per symbol (one row
per symbol, replaced each time). 204. Prices are typed in; Budget Buddy never fetches them.

## Retirement and HSA contributions

`GET /api/local/retirement/{tax_year}`: one line each for 401(k)/403(b)/457 deferrals (pay-stub
`retirement_cents` + `roth_retirement_cents`, by pay date), IRA (`ira` deductions for the year), HSA self-only and
HSA family (pay-stub `hsa_cents` + `hsa` deductions): contributed, limit, room left, amount over, catch-up amounts
(listed, never added: age isn't known). Every limit comes from the year's tax data file (`retirement`, `hsa`); a
year without one is 404 `no_tax_data`. Employer matches and Roth IRA contributions aren't seen; the note says so.
