# Investments: holdings, prices, retirement limits

Code: `services/stock_holdings.py`, `services/retirement.py`, `routers/stocks.py` (holdings, prices),
`routers/retirement.py`, `services/price_feed.py`, tables `stock_prices` (migration 0015) and `price_feed`
(migration 0017). Dashboard: `screens/investments.js` (Money,
Investments). User guide: [docs/guide/investments.md](../../guide/investments.md). Estimates, not tax advice.

## Holdings

- `GET /api/local/stocks/holdings`: per account (or "Not in an account"), each symbol still held: shares, the cost
  of the shares still held, the latest price, value and the gain or loss not yet sold; totals per account and
  overall (`value_cents` is null while any holding has no price). `taxed` is false for retirement accounts and HSAs.
- Remaining cost of a purchase = its cost minus `share_of(cost, sold, shares)`, the same half-up cumulative rounding
  as the gains ([stocks.md](stocks.md)), so cost held + cost sold is exactly the cost paid.
- Value = `share_of(price_cents, shares_micro, SHARES_SCALE)`: shares times the per-share price, half up to a cent.

## Prices

`POST /api/local/stocks/prices` `{symbol, price_cents | price, as_of}` saves a typed-in price (one row per
symbol, replaced each time; `source` "you"). 204.

## Live prices (`services/price_feed.py`, [ADR-0010](../../adr/0010-live-stock-prices.md))

- `GET/PUT /api/local/stocks/price-feed` `{enabled, api_key?}` (table `price_feed`, one row, migration 0017):
  off by default; the key is encrypted at rest, only `has_key` is returned, and `api_key: ""` removes it.
- `POST /api/local/stocks/prices/refresh`: if on and a key is saved, one HTTPS GET per held symbol to
  `https://finnhub.io/api/v1/quote` with the key in `X-Finnhub-Token` (5 s timeout, reply read up to 4 KB).
  Skips symbols fetched in the last 60 s. Saves `c` (latest price, half up to a cent) dated by `t`, with
  `source` "feed" and `fetched_at`. Returns `{updated, not_found, message}`; 401/403, 429 or no connection stop
  the refresh with a plain message, keeping prices fetched so far.
- The dashboard calls refresh when the Investments page opens and on Refresh prices; never on a timer.
- Holdings include `price_source` and `price_fetched_at`.

## Retirement and HSA contributions

`GET /api/local/retirement/{tax_year}`: one line each for 401(k)/403(b)/457 deferrals (pay-stub
`retirement_cents` + `roth_retirement_cents`, by pay date), IRA (`ira` deductions for the year), HSA self-only and
HSA family (pay-stub `hsa_cents` + `hsa` deductions): contributed, limit, room left, amount over, catch-up amounts
(listed, never added: age isn't known). Every limit comes from the year's tax data file (`retirement`, `hsa`); a
year without one is 404 `no_tax_data`. Employer matches and Roth IRA contributions aren't seen; the note says so.
