# Transfers: matching and kinds

Code: `services/ledger/transfers.py` (link, unlink, `pair_up`), `services/ledger/transfer_matching.py` (automatic matching),
`services/ledger/transfer_words.py` (the words), `services/ledger/transfer_categories.py` (which category a pair goes
in), `services/ledger/card_payments.py` (card payments under "Payments"), `app/transfer_types.py` (kinds), migration 0016 (`transactions.auto_transfer_off`). Routes and lock rules:
[ledger.md](ledger.md). User guide: [docs/guide/transfers.md](../../guide/transfers.md).

## Automatic matching

`match_transfers(session, only_ids)` links pairs that are:

- one money-out and one money-in transaction for exactly the same amount, on different accounts, dated at most
  `WINDOW_DAYS` (5) apart;
- both `normal`, unlinked, not a paycheck's deposit, a linked donation or a dividend's deposit sweep, not unlinked by the user before
  (`auto_transfer_off`), and uncategorized or in a transfer-group category (a category from the user or a rule
  is respected);
- at least one description matches `TRANSFER_WORDS`; a credit card's side matches `CARD_PAYMENT_WORDS` (a refund
  isn't a payment); neither matches `NOT_TRANSFER_WORDS` (dividends, interest, employer match, payroll, refunds,
  cash back);
- money leaving any account but a credit card or loan;
- each other's single best match: the closest date wins; a tie on either side links nothing.

It runs after a CSV import (pairs with at least one imported row; `ImportResult.transfers_matched`), after
`POST /api/local/transactions` (that transaction), and on `POST /api/local/transactions/match-transfers` (all;
`{"matched": N}`). Linked pairs get kind `transfer`, a transfer-group category ("Payments" for a card payment,
else "Transfer"; see below), and `category_source` None (Budget Buddy's choice). Linking (automatic or by hand) keeps each side's previous category, source and rule in
`pre_transfer_*`; unlinking puts them back and sets `auto_transfer_off` on both sides; linking by hand clears it.

## Card payments: the "Payments" category

A card payment goes in "Payments" (transfer group, so never spending or income; made the first time by
`named_categories.find_or_make`) on both sides, linked or not:

- `transfer_categories.pair_category`: a pair whose money goes into a credit card (`classify` gives `card_payment`)
  gets "Payments" instead of "Transfer" when linked.
- `card_payments.file_card_payments(session, only_ids)` runs at the end of `match_transfers`: an uncategorized
  transaction that's `transaction_roles.free_to_move()` (shared with matching: `normal`, unlinked, not
  `auto_transfer_off`, not a paycheck deposit, donation, dividend sweep or trade) and not a dividend goes in
  "Payments" when it's money into a credit card matching `CARD_SIDE_WORDS` (not `NOT_CARD_SIDE_WORDS`: a merchant's
  credit or adjustment; not `NOT_TRANSFER_WORDS`), or money out of any account but a card or loan (`CANT_SEND`)
  matching `CARD_PAYMENT_WORDS` and `CARD_WORDS` (it names a credit card; never the bare word "card"), not
  `NOT_CARD_PAYMENT_WORDS` (debit-card purchases, loans, savings at a card lender) or `NOT_TRANSFER_WORDS`, and
  sharing a word with one of your card accounts' name or institution (`your_card_words`, minus `GENERIC_WORDS`,
  with `ISSUER_ALIASES` like amex = american express): a payment to a card you haven't added is the only record of
  its spending. A returned payment (`RETURNED_WORDS`: money back into the bank, or out of the card) is filed too;
  a fee (`FEE_WORDS`) never is. Words: `transfer_words.py`. On a full run (no `only_ids`: Find transfers, Match
  everything again) it also moves both sides of linked card payments still in Budget Buddy's "Transfer"
  (`category_source` None) to "Payments", for older data.
- Clearing the category of a line in Budget Buddy's transfer-group category (source None) sets `auto_transfer_off`
  (`transactions.update_transaction`), so it isn't filed or matched again.
- `pair_category` looks the two categories up once per matching run (`known`), and the "Transfer" fallback never
  picks "Payments".
- Import results' `categorized` counts only lines an auto-sort rule sorted (`category_source` "rule").
- A "Payments" category of yours in another group is never used: pairs get "Transfer" and nothing is filed.
- Still eligible for matching (a transfer-group category), so a filed side links when its other side comes in;
  unlinking puts back the category from before the link ("Payments" if it was filed first).

## Kinds

`transfer_type` on each side of a linked transfer, worked out from the two accounts (never stored): where the
money went decides first (`card_payment`, `loan_payment`, `to_savings`, `to_investments`, `to_retirement`,
`to_hsa`), else where it came from (`from_savings`, `from_investments`, `from_retirement`, `from_hsa`), else
`between_accounts`. It's a label; what counts as saved is `services/ledger/savings_transfers.py` (into savings-type
accounts from everyday ones).
