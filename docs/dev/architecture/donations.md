# Charitable donations (roadmap #11)

Code: `services/donations.py`, `schemas/donations.py`, `routers/donations.py`. Estimates, not tax advice.
User guide: [docs/guide/donations.md](../../guide/donations.md).

## Routes (this computer only)

- `GET/POST /api/local/donations` (filters: `tax_year`, `kind`, `limit`, `offset`; newest first) and
  `GET/PATCH/DELETE /api/local/donations/{id}`.
- `GET /api/local/donations/summary/{tax_year}`.

## A gift

A date, the charity's name (`organization`), a kind (`cash` or `goods`), an amount (`amount_cents`, or `amount` as
dollar text; for goods, the items' fair market value), and optionally a `receipt_id` and notes (encrypted).

- The amount must be more than zero.
- The date can't be more than one day after the Home Base's date (pledges count once paid).

## Yearly summary

- Totals what was given that calendar year (cash, goods, overall) and lists the proof each gift needs.
- Adds the paperwork that depends on the whole year: Form 8283, the "check similar items" note, and the 2026+
  note for people who don't itemize.
- **Every dollar threshold comes from that year's tax data file** (`charitable` section;
  [../tax-data.md](../tax-data.md)); changing a threshold there changes the flags with no code change. A year
  without a file gets 404 `no_tax_data`. If `non_itemizer_deduction_cents` is `null`, the non-itemizer note is
  left out.
- Totals are **what was given, not what can be deducted**, and every summary is labeled an estimate
  (`is_estimate`, `disclaimer`).

The phone snapshot's `donations_total_cents` comes from this service (sync contract §5).
