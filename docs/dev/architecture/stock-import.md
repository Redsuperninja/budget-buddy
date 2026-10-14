# Stock CSV import (roadmap #12d)

Code: `services/imports/stock_csv.py` (find the columns, read one row), `services/imports/stock_import.py` (preview,
duplicates, add), `schemas/imports/stock_import.py`, `routers/imports/stock_import.py`. Decoding, row splitting, amounts and dates
are shared with the bank import (`services/imports/csv_parsing.py`, [csv-import.md](csv-import.md)); the upload checks
(CSV content type, 5 MB, 10,000 rows) are the same dependency (`routers/imports/csv_import.CsvBody`). User guide:
[docs/guide/import-stocks.md](../../guide/import-stocks.md).

## Routes (this computer only)

The request body is the CSV file. Query: `account_id` (optional; the shares' account).

- `POST /api/local/stocks/import/preview`: the columns found, counts (`new_buys`, `new_sells`,
  `duplicate_rows`, `invalid_rows`) and the first 50 rows plus up to 100 more with a problem. Saves nothing.
- `POST /api/local/stocks/import`: adds every new row in one database transaction. `skip_invalid_rows=true` to
  skip rows that can't be read; otherwise any such row refuses the import (422 `invalid_rows`).

## Rules

- **Columns from the header row only** (the first of the top 10 rows that names them all); no column picker.
  Symbol: "symbol", "ticker". Date: "trade date", "date acquired", "acquired", "purchase date", "date sold",
  "transaction date", "run date", ..., "date", never one with "settle" in it (the holding period runs from the
  trade date). Shares: "quantity", "shares", "qty", "units". Money (the row's total): "cost basis", "total cost",
  "proceeds", "net amount", "amount", "cost", "total", never one naming a price, per share, average, unit, fee
  or commission. Optional type column, named exactly "type", "action", "buy sell", "side", "transaction type" or
  "activity" (so "Security Type" isn't used); its cells must contain the whole word buy/bought/purchase/
  reinvest or sell/sold/sale, and never short, cover, open, close, option, call, put, exercise, assign, cancel,
  cxl or correction (short sales, options and corrections are entered by hand). Without it every row is a
  purchase. 422 `columns_not_found` if no row names all four.
- **Each row is checked by `LotCreate`/`SaleCreate`**, the same schemas as typing a purchase or sale in, so the
  symbol, share (6 decimal places) and cents rules are identical. Signs are dropped from money (brokers show buys
  as negative amounts) and from shares on a sale (`-5`, `(5)` or `5-`); negative shares with no type column, or
  on a buy, make the row invalid. Thousands commas are allowed.
- **Duplicates** are found by comparing with the account's existing purchases and sales (type, symbol, date,
  shares, money), counted: a re-import adds nothing, two identical rows in one file are both kept. No new
  columns or tables.
- **FIFO**: after adding, each symbol is re-matched (`stock_records.rematch`). A sale that needs more shares than
  were held rolls the whole import back (422 `not_enough_shares`, naming the symbol and date).
- Nothing logs file contents; error messages name rows and problems, never cell contents.
