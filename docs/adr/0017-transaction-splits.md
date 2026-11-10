# ADR-0017: Transaction splits: parts that add up to the transaction

**Status:** Proposed, 2026-11-10 (roadmap 10f; issues #16 and #30).

## Context
A transaction has one `category_id`. Real payments often cover several things: a store run that is groceries and
household, or a $1,500 mortgage payment from checking that is $1,200 of principal (money moved to the loan) and
$300 of interest (spending, issue #30). Every total by category reads `Transaction.category_id` directly: the
monthly summary (`services/budget/summary.py`, which the budget engine, Home charts and the phone snapshot's
`budget` use), the spending pace, the Transactions page's category and "no category yet" filters, auto-sort rules
and learning, transfer, card-payment and dividend matching, pay-deposit detection, gift categories and deleting a
category. Tax totals (donations, deductions) come from their own tables, not from categories.

## Decision (proposed)
1. **A new table** `transaction_splits(id, transaction_id, category_id, amount_cents, note)`. A transaction with
   split rows is split; one without behaves exactly as today. A split transaction's own `category_id` is `NULL` and
   ignored. `transaction_id` cascades on delete; `category_id` has a foreign key and a category used by a part
   can't be deleted (the existing "in use" check gains splits). `note` is an `EncryptedString`
   ("transaction_splits.note"), like `transactions.notes`. Amounts are integer cents, not encrypted.
2. **Rules, checked in one service** (`services/ledger/splits.py`): 2 to 20 parts; every part nonzero with the
   same sign as the transaction; parts add up exactly to `amount_cents`. Only `normal` and `refund` transactions
   can be split. One route replaces the whole list: `PUT /api/local/transactions/{id}/splits` (an empty list
   undoes the split; the transaction then has no category). While split, setting `category_id` or changing the
   amount is a 409 `split_transaction` with a plain-English message: change or undo the split first.
3. **One shared reader for category totals:** `services/budget/category_lines.py` gives one row per category line
   (an unsplit transaction, or each part of a split one) with the transaction's date, kind and account. The
   summary, spending pace and category filter use it instead of `Transaction.category_id`. Each line follows
   today's rules: **its category's group decides** income, spending or ignored (transfer group); a refund's parts
   net against spending and a refund part in an income category is unassigned, as today.
4. **Leave split transactions alone elsewhere:** auto-sort rules, learning, the "no category yet" filter, transfer,
   card-payment and dividend matching skip them. Imports never split (rules set one category). Sorting into
   charity, recording a stock trade or a dividend on a split transaction is refused for now.
5. **Loan payments (#30):** a split part in the Transfer category can be linked to the loan account's matching
   deposit (+$1,200) through the existing transfer link: both sides get `transfer_pair_id`; the loan side becomes
   a `transfer` as today; the split side stays `normal` so its interest part still counts as spending, and its
   Transfer part is ignored like any transfer-group line. While linked, the split is locked like a transfer.
   Loan principal is not "saved" (same as loan payments today, roadmap 10b).
6. **Phone sync contract: no change.** The budget totals are computed on the Home Base, so the phone's numbers are
   right. In `transactions`, a split transaction has `category_id: null` (the phone shows "No category").
   Sending the parts waits for contract v2 (roadmap 30).

## Consequences
- Unsplit transactions, imports and all existing tests are unchanged; the new paths get their own tests,
  including summary-equivalence tests (a split into one category equals the unsplit transaction).
- Every new reader of categories must use `category_lines`; `docs/dev/architecture/budget-summary.md` says so.
- Account balances, net worth and backups are unaffected (the amount is still on the transaction; backups copy
  the whole database).
- SQLite can't check sums across rows, so the sum rule lives only in the service; a test covers every write path.
- The phone's "No category" label for split transactions is a known gap until contract v2.
