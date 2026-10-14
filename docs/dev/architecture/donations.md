# Charitable donations (roadmap #11)

Code: `services/tax/donations.py`, `services/tax/donation_proof.py` (paperwork rules), `services/tax/donation_payments.py`
(gifts from payments), `services/tax/gift_categories.py`, `schemas/tax/donations.py`, `routers/tax/donations.py`. Estimates,
not tax advice.
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
`services/tax/donation_payments.py`, checked on the final values of a create or PATCH):

- The payment must be a regular (`normal`) transaction with money going out; otherwise 422 `invalid_payment`.
- The gift must be `cash`, and no more than the payment (the rest may have bought something, like a dinner).
- One payment backs one gift (unique column; a second link is 409 `already_linked`, also when two saves race).
- Deleting the payment keeps the gift and clears the link (`ON DELETE SET NULL`). While linked, the payment's
  amount and kind are locked and it can't become a transfer ([ledger.md](ledger.md)).
- The gift keeps its own date: the dashboard starts it at the payment's date but lets people change it, since a
  bank may show when a check cleared rather than when it was mailed. Don't tie the two dates together.
- A gift smaller than its payment (something came back) adds the `quid_pro_quo_statement` paperwork item.
- A newly linked payment is filed under the "Charitable giving" category;
  `POST /api/local/transactions/{id}/personal-gift` files a payment under "Gifts" with no donation (409 if it's already a charity gift). Both are
  wants-group categories found by name (case ignored) or made on first use; a same-named income or transfer
  category is never used: a charity link still saves (the payment keeps its category), a personal gift is
  409 `name_taken` (`services/tax/gift_categories.py`). Unlinking or re-pointing a gift leaves the old payment in
  "Charitable giving"; it isn't moved back.
- Transactions show the link as `donation_id`. The payment still counts once as spending; the gift is a tax
  record, not a second expense.

## Recurring gifts (`services/tax/repeat_gifts.py`)

After a bank file is imported, and after a transaction is added by hand, each **new** regular money-out payment
whose `shop_key` (the start of the description, as in auto-sort learning) matches a payment you linked to a cash
gift for the **whole** payment is filed under "Charitable giving" with `category_source` null (Budget Buddy's
choice, so learning ignores it). If it's the same amount as the newest such gift it also gets a cash donation: the
charity's name from that gift, the payment's date, the whole payment, `auto_added = true` (migration 0024). A
different amount is only filed (it may include perks). Keys that name a payment method (`NOT_A_PAYEE`: CHECK,
ZELLE, VENMO, TRANSFER and so on) are never used, nor a key with any part gift (a gala billed like the monthly gift). Transfers, refunds, adjustments, stock trades and payments
already linked to a gift are skipped. Old payments are never looked at again, so deleting an automatic donation is
final. The import result has `donations_added`.

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
