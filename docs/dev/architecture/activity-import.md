# Brokerage activity import (roadmap 26b)

Code: `services/activity_csv.py` (columns by name, one row), `services/activity_import.py` (preview, duplicates,
add and sort), `schemas/activity_import.py`, `routers/activity_import.py`. Shared: decoding, amounts, dates and
fingerprints (`csv_parsing`), header matching (`csv_headers`), Buy/Sell wording and share signs (`stock_csv`),
upload checks (`CsvBody`). Dashboard: **Money**, **Import files** (`screens/activity-import.js`). User guide:
[docs/guide/import-brokerage-activity.md](../../guide/import-brokerage-activity.md).

## Routes (this computer, or a joined one: the `accounts` area)

- `POST /api/local/accounts/{id}/activity-import/preview`: columns found, counts (`new_rows`, `new_trades`,
  `duplicate_rows`, `invalid_rows`) and the first 50 rows plus up to 100 with a problem.
- `POST /api/local/accounts/{id}/activity-import?skip_invalid_rows=&file_name=`: add it all, or none.
- Only brokerage, retirement and HSA accounts (422 `not_an_investment_account`).

## Rules

- **Columns** (first 10 rows): date ("run date", "trade date", "transaction date", "activity date", "date"; never
  "settle"), action ("action", "activity", "transaction type", "type", "transaction") and amount ("amount", "net
  amount", "total"; never price, commission, fee, per share or accrued) are required; symbol, quantity and the
  security's description are optional.
- **Every row** with money moving is a `normal` transaction (`source = csv`): wording = action, plus the security's
  name and `(SYMBOL)` when the action doesn't already say them; amount as signed in the file. Rows with no money
  (shares journaled in, splits) are `skipped`, not invalid. Duplicates use the bank import's fingerprint, so overlapping files are safe.
- **Stock trades**: a row whose action is a plain buy or sell (`stock_csv.trade_kind`: never short, cover, open,
  options, cancel or corrections), with a symbol and shares, money out for a buy and in for a sale, also becomes a
  lot or sale order linked to its transaction (`transaction_id`, as in [stocks.md](stocks.md)) and to the import.
  Cost basis = the amount paid; proceeds = the amount received. Never for a money market fund (a 3-letter + "XX"
  symbol, or "money market", "core account" or "sweep" wording): that's the account's cash. A matching lot or sale
  already there with no transaction (same account, symbol, date, shares, cents) is linked instead of added. Trades get no category (they stay out of the
  budget). Each symbol is matched again with FIFO; a sale needing more shares than held stops the import (422
  `not_enough_shares`).
- **The rest** is sorted like a bank import: auto-sort rules, then dividends and their sweeps
  ([dividends.md](dividends.md)), then transfers ([transfers.md](transfers.md)).
- Recorded in the import history (kind `activity`), so it can be undone ([imports.md](imports.md)).
