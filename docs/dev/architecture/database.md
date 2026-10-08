# Database and migrations

- One SQLite file, `budget.db`, in the data folder ([server.md](server.md)). Tables: [data-model.md](data-model.md).
- The schema is managed by Alembic (`server/app/migrations/`) and **upgraded automatically when the Home Base
  starts**, under a lock file so only one copy migrates at a time. Nobody runs migrations by hand.
  A database already at a revision this copy doesn't know (a newer Budget Buddy opened it) is left alone, with a
  plain message to update this copy (for example an older built desktop app).
- Before upgrading an existing database, a copy `budget.db.bak-<revision>` is saved next to it. Users may delete
  old copies once Budget Buddy works (the ones from before migration 0003 are not encrypted;
  [security.md](security.md)).

## Migrations so far

| Revision | What it does |
| --- | --- |
| 0001 | Initial tables |
| 0002 | Seed default budget categories |
| 0003 | Encrypt sensitive columns (ADR-0003) |
| 0004 | Bank CSV import: `import_fingerprint`, `csv_import_mappings` |
| 0005 | Paycheck details: health insurance, Roth, linked deposit |
| 0006 | Phone pairing: `devices` columns, `pairing_sessions`, `pairing_nonces` |
| 0007 | Stock sales as entered: `stock_sale_orders`, `stock_sales.order_id` |
| 0008 | Encrypted sync: `seen_nonces`, `devices.nonce_watermark`, `receipts.client_id` / `deduction_kind` / `device_id` |

## Adding a migration

1. Edit the models in `server/app/models/`.
2. Generate a migration and check it by hand:

   ```powershell
   .venv\Scripts\alembic revision --autogenerate -m "describe the change"
   ```

3. Number it after the last one and add a test. Never edit a migration that has shipped: migrations are history.
4. Update [data-model.md](data-model.md) and this table.
