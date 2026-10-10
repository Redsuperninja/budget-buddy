# Positions from a broker's file (roadmap #12g)

Code: `services/positions_csv.py` (find columns, read a line), `services/positions.py` (preview, import, list,
clear), `services/csv_headers.py` (header matching shared with the stock import), `schemas/positions.py`,
`routers/positions.py`. Upload checks are the bank import's (`CsvBody`). User guide:
[docs/guide/investments.md](../../guide/investments.md).

## Routes (this computer, or a joined one: the `stocks` area)

Query for both imports: `account_id` (required) and `as_of` (the day the file is from; files rarely say; not in
the future).

- `POST /api/local/stocks/positions/import/preview`: columns found, positions (one per symbol), skipped lines.
- `POST /api/local/stocks/positions/import`: replace the account's snapshot; returns counts and `prices_updated`.
- `GET /api/local/stocks/positions`: each account's snapshot, with `recorded_shares_micro` (that account's
  purchases minus sales of the symbol dated on or before `as_of`, so later trades don't look missing) and `matches`,
  both ways: symbols you hold by your records that the file leaves out are added with `in_file: false` and 0
  shares. Each account has `bank_trades_waiting` (bank-file trades on or before `as_of` with no shares yet).
- Stock purchases and sales (`GET /stocks/lots`, `/stocks/sales`, the gains summary) carry `checked_by`:
  `"transaction"` (linked to a transaction), `"positions_file"` (the account's file agrees for that symbol, same
  shares or none on both sides, and is dated on or after the trade) or null. Worked out each time in
  `services/holdings_check.py`, never stored.
- `DELETE /api/local/stocks/positions/{account_id}`: forget an account's snapshot.

## Rules

- **A snapshot, not trades.** `positions` (migration 0021) never feeds lots, sales, gains or holdings; it's shown
  beside them. Importing replaces every line for that account; deleting the account removes them (cascade).
- **Columns by name** (first 10 rows): symbol ("symbol", "ticker") and shares ("quantity", "shares", "qty",
  "units") are required; optional cost ("cost basis total", "total cost basis", "cost basis", "total cost"; never
  per share, average, avg or unit), value ("current value", "market value", "total value", "value"; never change,
  gain, percent or per share) and price ("last price", "current price", "market price", "price"; never change).
- **Lines skipped, not refused**: a symbol that isn't a valid ticker (after dropping trailing `*`, as in
  Fidelity's `SPAXX**`), no or negative shares (cash, short positions), and notes. The same symbol on several
  lines is added up; a cost or value missing on any of them makes the total unknown (`null`).
- **Prices**: a line's price becomes the symbol's `StockPrice` with source `file`, unless a price dated after
  `as_of`, or a live (`feed`) price from the same day, is saved. Value shown = the file's value, else shares x the
  latest price (today's, not the file's).
