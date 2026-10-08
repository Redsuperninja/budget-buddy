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

## A gift from a payment (sorting a transaction into charity)

`transaction_id` links a gift to the bank or card payment it was (migration 0012; rules in
`services/donation_payments.py`, checked on the final values of a create or PATCH):

- The payment must be a regular (`normal`) transaction with money going out; otherwise 422 `invalid_payment`.
- The gift must be `cash`, and no more than the payment (the rest may have bought something, like a dinner).
- One payment backs one gift (unique column; a second link is 409 `already_linked`, also when two saves race).
- Deleting the payment keeps the gift and clears the link (`ON DELETE SET NULL`). While linked, the payment's
  amount and kind are locked and it can't become a transfer ([ledger.md](ledger.md)).
- The gift keeps its own date: the dashboard starts it at the payment's date but lets people change it, since a
  bank may show when a check cleared rather than when it was mailed. Don't tie the two dates together.
- A gift smaller than its payment (something came back) adds the `quid_pro_quo_statement` paperwork item.
- Transactions show the link as `donation_id`. The payment still counts as spending in its category; the gift
  is a tax record, not a second expense.

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
