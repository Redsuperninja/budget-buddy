# Transfers: matching and kinds

Code: `services/transfers.py` (link, unlink, `pair_up`), `services/transfer_matching.py` (automatic matching),
`app/transfer_types.py` (kinds), migration 0016 (`transactions.auto_transfer_off`). Routes and lock rules:
[ledger.md](ledger.md). User guide: [docs/guide/transfers.md](../../guide/transfers.md).

## Automatic matching

`match_transfers(session, only_ids)` links pairs that are:

- one money-out and one money-in transaction for exactly the same amount, on different accounts, dated at most
  `WINDOW_DAYS` (4) apart;
- both `normal`, unlinked, not a paycheck's deposit or a linked donation, not unlinked by the user before
  (`auto_transfer_off`), and not in a category the user picked (`category_source` "you") unless it's a transfer
  category;
- money leaving any account but a credit card or loan;
- each other's single best match: the closest date wins; a tie on either side links nothing.

It runs after a CSV import (pairs with at least one imported row; `ImportResult.transfers_matched`), after
`POST /api/local/transactions` (that transaction), and on `POST /api/local/transactions/match-transfers` (all;
`{"matched": N}`). Linked pairs get kind `transfer`, the transfer category, and `category_source` None (Budget
Buddy's choice). Unlinking sets `auto_transfer_off` on both sides; linking by hand clears it.

## Kinds

`transfer_type` on each side of a linked transfer, worked out from the two accounts (never stored): where the
money went decides first (`card_payment`, `loan_payment`, `to_savings`, `to_investments`, `to_retirement`,
`to_hsa`), else where it came from (`from_savings`, `from_investments`, `from_retirement`, `from_hsa`), else
`between_accounts`. It's a label; what counts as saved is `services/savings_transfers.py` (into savings-type
accounts from everyday ones).
