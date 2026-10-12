# Import history and undo (roadmap 6b)

Code: `models/imports.py`, `services/imports/history.py`, `schemas/imports/history.py`, `routers/imports/history.py`; recorded by
`csv_import.commit` (kind `bank`), `stock_import.commit` (`stocks`), `positions.commit` (`positions`) and the
brokerage activity import (`activity`). Dashboard: **Money**, **Import history** (`screens/money/import-history.js`). User
guide: [docs/guide/import-history.md](../../guide/import-history.md).

## Routes (this computer, or a joined one: the `imports` area)

- `GET /api/local/imports`: every import, newest first: kind, account, file name, rows added, when.
- `DELETE /api/local/imports/{id}`: undo it (204), or 409 `import_in_use` when a sale from elsewhere needs shares it
  added. All or nothing.
- The imports' commit routes take an optional `file_name` (up to 200 characters, as the browser gives it).

## Rules

- **Table** (migration 0022): `imports` (kind, account_id `SET NULL`, file_name, rows_added). `transactions`,
  `stock_lots`, `stock_sale_orders` and `positions` get `import_id` (indexed, no foreign keys: no table rebuilds).
- An import that adds nothing isn't recorded. A new positions file for an account replaces the old snapshot, so
  the old file's entry is removed too.
- **Undo** deletes the import's rows with bulk deletes, so the database's own rules apply: paycheck deposit and
  donation links are cleared (`SET NULL`), dividend records go (`CASCADE`), sweeps and transfer pairs are cleared.
  Before that, a transfer partner outside the import is set back to a normal transaction with its earlier
  category (`transfers.unlink_sides`, without blocking future matching), and a stock trade from elsewhere linked to
  one of its transactions keeps its shares but loses the link. Its own trades are deleted and each affected symbol
  and account is matched again with FIFO.
- File names are cleaned (control and direction-changing characters removed, at most 200 characters), stored
  encrypted (`imports.file_name`: bank file names often hold account digits), shown only in the history, and
  never logged.
