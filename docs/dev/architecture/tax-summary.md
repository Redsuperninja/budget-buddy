# Other deductions and the yearly tax summary

Code: `services/tax/deductions.py`, `services/tax/tax_summary.py`, `services/tax/tax_export.py` and their routers.
Roadmap item 13. An estimate to gather records, not tax advice.

## Routes (this computer and joined computers, ADR-0009; never phones)

- `GET /api/local/deductions?tax_year=YYYY` (required), `POST /api/local/deductions`,
  `GET/PATCH/DELETE /api/local/deductions/{id}`. A deduction has `tax_year`, `kind` (see `DeductionKind`),
  optional `description` (up to 200 characters, encrypted at rest because it can hold health details;
  migration 0011), optional `date` (must be in `tax_year`), `amount_cents` or
  `amount` (dollars text, not negative), optional `receipt_id`. Listed by date, undated last.
- `GET /api/local/tax-summary/{year}`: pay-stub totals for the year, donation totals (cash, goods, all),
  realized stock gains (short, long, total, possible wash sales), other deductions by kind, the chosen
  `filing_status` (or `null`), and the basic standard deduction from that year's tax data (`null` without a data
  file): for every filing status, or only for `filing_status` when one is chosen. Works for any year from 2000
  to 2100; only the standard deduction needs tax data.
- `GET /api/local/tax-summary/{year}/export.csv`: the same year as a CSV download (see below). It has no
  standard deduction, so the filing status doesn't change it.
- `GET/PUT /api/local/tax-preferences` (roadmap 25j): `{"filing_status": "single" | "married_filing_jointly" |
  "married_filing_separately" | "head_of_household" | null}`; `null` (the default) is "Not set: show all".
  The allowed values are `FILING_STATUSES` in `app/tax_data`; qualifying surviving spouse isn't one because
  the data files don't list it. Unknown values or fields get 422. PUT needs the page's `Origin` and CSRF
  token like every write.

## Filing status (roadmap 25j)

- Stored in `tax_preferences` (migration 0030): one row (id 1, made when first saved), `filing_status`
  nullable with a CHECK on the four values. A typed single-row table, like `price_feed` and `setup_progress`,
  rather than a key/value settings table: the database checks the value, and there is only one setting.
- One status for every year shown (not one per year).
- **Display only**: it picks which status's numbers the summary returns; no amount is worked out differently.
- Not encrypted (one of four fixed words). Backups carry it and a restore brings back the backup's value,
  like other data. Because a key change can't make it unreadable, a row there doesn't count as the folder's
  own data (`_STARTER_TABLES` in `backup/restore.py`), so choosing a status on a new computer doesn't block
  restoring another key's backup.
- Joined computers may read and change it (`tax-preferences` is in `JOINED_AREAS`): they already see and edit
  the summary it narrows, and it opens no connection and lets nothing in. Phones never reach `/api/local`.

## Rules

- **Kinds are never added together.** Each kind has a `where` hint: `itemized` (medical, mortgage interest,
  property tax, state and local taxes: Schedule A, with limits such as the medical floor and the SALT cap),
  `adjustment` (student loan interest, HSA, IRA: can lower income without itemizing, within limits), `credit`
  (education, childcare), or `other` (home office, other). HSA, IRA and Other have their own text (HSA: only
  money put in yourself, not through payroll; IRA: traditional only, may be limited with a workplace plan).
  The mapping and plain-English text (`hint()`) live in
  `services/tax/deductions.py`; the phone snapshot's deduction labels come from the same place.
- Pay totals reuse the paychecks year summary; stock gains reuse `stock_sales.gains_summary`; donations are
  totaled by date in the calendar year (the same rule as the donations page).

## CSV export

- Columns: `Section, Item, Date, Amount ($), Notes`. One row per pay-stub total, donation, part of a stock sale
  (one per purchase lot, with term, proceeds, cost basis and any wash-sale flag), and other deduction, then the
  disclaimer.
- Amounts are plain dollars (`1234.56`, losses negative). UTF-8 with a byte-order mark so Excel shows accents.
- **Formula guard** (`app/spreadsheet.py`, shared with the CSV import): text cells (Item, Notes) starting with `=`, `+`, `-`, `@`, tab or carriage return get a
  leading `'`, so a spreadsheet never runs them.
- Sent with `Content-Disposition: attachment` and `Cache-Control: no-store`. Nothing is logged.

## PDF

There is no PDF library (no new dependency). The dashboard's Tax summary page has "Print or save as PDF",
which uses the browser's print dialog; print styles hide navigation, forms and buttons.
