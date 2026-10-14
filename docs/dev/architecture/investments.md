# Investments: holdings, prices, retirement limits

Code: `services/investing/stock_holdings.py`, `services/investing/retirement.py`, `routers/investing/stocks.py` (holdings, prices),
`routers/investing/retirement.py`, `services/investing/price_feed.py`, tables `stock_prices` (migration 0015) and `price_feed`
(migration 0017). Dashboard: `screens/money/investments.js` (Money,
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

## Live prices (`services/investing/price_feed.py`, [ADR-0010](../../adr/0010-live-stock-prices.md))

- `GET/PUT /api/local/price-feed` `{enabled, api_key?}` (table `price_feed`, one row, migration 0017): this
  computer only (not on the joined computers' allow-list); off by default; the key is encrypted at rest, only
  `has_key` is returned, and `api_key: ""` removes it.
- `POST /api/local/stocks/prices/refresh` (joined computers too): if on and a key is saved, one HTTPS GET per
  held symbol (at most 50, skipping any fetched in the last 60 s) to `https://finnhub.io/api/v1/quote` with the key
  in `X-Finnhub-Token`. The opener never follows redirects (urllib would copy the header) and always checks
  certificates; 5 s timeout, reply read up to 4 KB, NaN/Infinity refused. A price must be finite, above zero and at
  most $1 billion, and its time no later than tomorrow, or the symbol counts as not found. All quotes are fetched
  first and saved in one short transaction afterwards (no database lock while waiting on the internet); one
  refresh runs at a time. Returns `{enabled, updated, not_found, message}`; 401 (bad key), 429 or no connection
  stop early with a plain message, keeping prices fetched so far. 403 is Finnhub's "your plan doesn't cover this
  symbol" (mutual funds, stocks outside the US): that symbol goes in `not_found` and the refresh goes on.
- The dashboard calls refresh when the Investments page opens and on Refresh prices; never on a timer. A failed
  refresh becomes a note; the page still shows. The key box uses `autocomplete="new-password"`.
- Holdings include `price_source` and `price_fetched_at`.

## Retirement and HSA contributions

`GET /api/local/retirement/{tax_year}`: one line each for 401(k)/403(b)/457 deferrals (pay-stub
`retirement_cents` + `roth_retirement_cents`, by pay date), IRA (`ira` deductions for the year, plus money into accounts with `retirement_type = roth_ira`: linked
transfers in, and `normal` deposits whose description says "contrib", never rollovers, conversions or
recharacterizations; by transaction date), HSA self-only and
HSA family (pay-stub `hsa_cents` + `hsa` deductions): contributed, limit, room left, amount over, catch-up amounts
(listed, never added: age isn't known). Every limit comes from the year's tax data file (`retirement`, `hsa`); a
year without one is 404 `no_tax_data`. Employer matches aren't seen; the note says so.
