# Other deductions and the yearly tax summary

Code: `services/deductions.py`, `services/tax_summary.py`, `services/tax_export.py` and their routers.
Roadmap item 13. An estimate to gather records, not tax advice.

## Routes (this computer only)

- `GET /api/local/deductions?tax_year=YYYY` (required), `POST /api/local/deductions`,
  `GET/PATCH/DELETE /api/local/deductions/{id}`. A deduction has `tax_year`, `kind` (see `DeductionKind`),
  optional `description` (up to 200 characters, encrypted at rest because it can hold health details;
  migration 0011), optional `date` (must be in `tax_year`), `amount_cents` or
  `amount` (dollars text, not negative), optional `receipt_id`. Listed by date, undated last.
- `GET /api/local/tax-summary/{year}`: pay-stub totals for the year, donation totals (cash, goods, all),
  realized stock gains (short, long, total, possible wash sales), other deductions by kind, and the basic
  standard deduction for each filing status from that year's tax data (`null` without a data file). Works for
  any year from 2000 to 2100; only the standard deduction needs tax data.
- `GET /api/local/tax-summary/{year}/export.csv`: the same year as a CSV download (see below).

## Rules

- **Kinds are never added together.** Each kind has a `where` hint: `itemized` (medical, mortgage interest,
  property tax, state and local taxes: Schedule A, with limits such as the medical floor and the SALT cap),
  `adjustment` (student loan interest, HSA, IRA: can lower income without itemizing, within limits), `credit`
  (education, childcare), or `other` (home office, other). HSA, IRA and Other have their own text (HSA: only
  money put in yourself, not through payroll; IRA: traditional only, may be limited with a workplace plan).
  The mapping and plain-English text (`hint()`) live in
  `services/deductions.py`; the phone snapshot's deduction labels come from the same place.
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
