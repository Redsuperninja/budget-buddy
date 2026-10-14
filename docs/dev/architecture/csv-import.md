# Bank CSV import

Code: `services/imports/csv_parsing.py` (decode, read rows, amounts, dates, fingerprint), `services/imports/csv_columns.py`
(guessing which column is what, date-format detection), `services/imports/csv_import.py` (limits, preview, commit,
saved mapping), `routers/imports/csv_import.py`. User guide: [docs/guide/](../../guide/).

## Routes (this computer only)

1. `POST /api/local/accounts/{id}/csv-import/preview`: the request body is the file itself
   (`Content-Type: text/csv`). Returns which column was taken as date, description and amount (or separate
   money-out and money-in columns) and every row it would add. Nothing is saved.
2. `POST /api/local/accounts/{id}/csv-import`: same file, same choices; saves the rows. With
   `save_mapping=true` the choices are saved for this account.
3. `DELETE /api/local/accounts/{id}/csv-import/mapping` forgets the saved mapping.

Query parameters override the guesses (both routes): `delimiter`, `header_rows`, `date_column`,
`description_column`, `amount_column` or `debit_column` + `credit_column` (numbered from 0), `date_format`
(e.g. `DD/MM/YYYY`), `flip_sign=true` (for card issuers that list charges as positive). The import route also
takes `save_mapping` and `skip_invalid_rows`.

For a `credit_card` account, unless `flip_sign` is given, the file is checked after reading
(`services/imports/card_signs.py`): it is flipped when most payment lines ("PAYMENT THANK YOU", "AUTOPAY", ...) are
money out, or, with no payment lines, when at least 80% of 3 or more amounts are money in. The preview then
has `mapping.flip_sign` turned over and says so in `message`; saving the mapping keeps the flip.

## Rules

- **Duplicates.** Each imported row stores a fingerprint (`transactions.import_fingerprint`, unique) of account,
  date, amount, description, and how many identical rows came before it in the file. Rows already present are
  skipped and counted as `skipped_duplicates`; two identical purchases on the same day in one file are both kept.
- **Dates.** US month/day is tried first. A day/month file where every day is ≤ 12 needs `date_format` set.
  Formats: `YYYY-MM-DD`, `MM/DD/YYYY`, `MM/DD/YY`, `DD/MM/YYYY`, `DD/MM/YY`, `YYYY/MM/DD`, `MM-DD-YYYY`,
  `DD.MM.YYYY`, `YYYYMMDD`, `Mon D, YYYY`, `D Mon YYYY` (a time after the date is ignored).
- **Amounts** may have `$`, thousands commas, `(12.34)` or `12.34-` for negatives. Anything that can't be read
  exactly (like `12,34` with a decimal comma) is never guessed: the row is a problem.
- **Problem rows** stop the import and are listed by row number, so nothing half-imports, unless
  `skip_invalid_rows=true`. Blank lines are ignored.
- **Limits:** 5 MB and 10,000 rows per file. UTF-8, UTF-16 and Windows-1252 are accepted.
- **Hidden characters:** control characters (C0 and C1) and the ones that flip text direction (U+202A-202E,
  U+2066-2069) become spaces in a description (`csv_parsing.clean_description`), so it can't read as something else.
- **Formula guard** (`app/spreadsheet.py`): a description starting with `=`, `+`, `-`, `@`, tab or carriage return gets a `'` in front, so a spreadsheet never
  runs it as a formula after export.
- Imported rows are `normal` transactions with `source = csv`, sorted into a category by the
  [auto-categorization rules](category-rules.md) where one matches (no category otherwise). Then dividends and their
  deposit sweeps are found ([dividends.md](dividends.md)), then transfers between accounts ([transfers.md](transfers.md)).
