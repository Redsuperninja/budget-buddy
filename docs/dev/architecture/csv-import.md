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

## Bank OFX/QFX import (roadmap 26-2, [ADR-0016](../../adr/0016-ofx-import.md))

Code: `services/imports/ofx_parsing.py` (the reader), `services/imports/ofx_import.py`, `routers/imports/ofx_import.py`,
`schemas/imports/ofx_import.py`, with `ofx_rows.py` (preview rows, look-alikes) and `ofx_signs.py` (backwards cards). The
upload check (type, early `Content-Length`, streamed byte limit) is `routers/imports/upload.py: read_upload`, shared with the CSV router. Same shape as the CSV import: preview, then save; nothing from the file is logged.

- Routes (this computer only; body is the file, `Content-Type` an OFX/QFX type, `text/plain` or `application/octet-stream`):
  `POST /api/local/accounts/{id}/ofx-import/preview` and `POST /api/local/accounts/{id}/ofx-import`. Query:
  `statement` (1-based, which account in a multi-account file), `flip_sign` (true/false, see Signs), and on save `confirm_account`, `skip_invalid_rows`,
  `file_name`. 5 MB cap (413 `file_too_large`), wrong type 415 `not_an_ofx`, unreadable 400 `unreadable_file`.
- **Account match.** Only the last 4 of the file's `ACCTID` are used (the bank id is ignored). If the account has
  `last4` saved, the file's statement must end the same (422 `wrong_account`, naming both). If it has none, the save needs
  `confirm_account=true` (422 `confirm_account`) and stores the 4 digits in the existing encrypted `accounts.last4`
  (digits only: otherwise 422 `account_digits`). A file with several accounts, or several matching, needs `statement`
  (422 `choose_statement`); the preview lists them with `chosen: null`.
- **Duplicates.** `import_fingerprint` = SHA-256 of `["ofx1", account id, FITID]` (no migration). A known ID with the
  same amount is a duplicate; with a different amount the row is flagged `invalid` (needs `skip_invalid_rows`), never
  merged. The wording is neutral ("already here with a different amount (it may have been edited)"), because the
  usual cause is the user editing the imported row. A zero amount is not a problem: it is counted (`zero_rows`, then
  `skipped_zero`) and left out. Reader notes ("left out") block the save unless `skip_invalid_rows`.
- **Per account.** Problem notes, `invalid_rows` and the save check belong to the chosen account only: a bad row or an
  account without digits elsewhere in the file never blocks or counts. Row numbers (and "Transaction N" notes) are the
  line's position among that account's transactions in the file, so they match the preview.
- **Earlier files are not matched** (ADR decision 3), so a bank that gives fresh IDs on every download can repeat rows. The
  preview `message` warns when the account has imported rows for those dates that aren't from this file (earlier bank
  file or CSV), and `possible_duplicate_rows` / `possible_duplicates` list new rows whose date and amount match an
  existing transaction. They are still added. The messages are joined, so the account-digits note doesn't hide them.
- **Signs.** OFX gives money out as negative, for cards too. A card (account kind or statement type) whose file looks
  backwards (`ofx_signs`: `TRNTYPE` DEBIT with a positive amount or CREDIT with a negative one, given at least
  `MIN_TYPED_ROWS` = 3 typed rows, **or** the CSV `looks_flipped` check: either one flags it) is never flipped silently: the preview has `looks_flipped: true`, a warning in `message` and the
  rows as the file has them; the save is refused (422 `choose_card_signs`) until the query has `flip_sign=true` or
  `false`. `flip_sign=true` on a non-card account is refused (422 `flip_not_for_this_account`). Re-importing a
  flipped file unflipped shows each row as invalid with "this file's signs differ from the earlier import" (the saved
  amount is exactly the file's negative), not as an edit. Rows are `source = csv` (the
  column's check constraint has no "ofx" value; it means "imported file"), `normal`, sorted by rules, then dividends,
  trades, transfers and repeat gifts as in CSV; history kind `bank`, so undo works.
- **OFX dates and time zones** (`ofx_parsing.parse_date`): the date the bank writes is kept and the time and zone are
  ignored. A bank that states a UTC timestamp near midnight (`20270101030000[0:GMT]` for an evening purchase on
  December 31 local time) lands the row on the next day, and a year-end purchase can move into the next tax year.
  Known, accepted risk: guessing a zone would be wrong as often, so the preview shows the date used. The guide page
  (26-5) must mention year-end dates.
