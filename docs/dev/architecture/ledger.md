# Accounts and transactions (the ledger)

Code: `services/accounts.py`, `services/transactions.py`, `routers/accounts.py`, `routers/transactions.py`.
Common API rules: [server.md](server.md).

## Transaction kinds and what counts as income or spending

- `normal`: everyday money in or out. Counts as income or spending, decided by its category's group.
- `refund`: money coming back for an earlier purchase. **Always positive.** It nets against spending in
  its category; it is never income.
- `transfer`: one half of a linked pair moving money between two of your own accounts. Never income or
  spending.
- `adjustment`: corrects a balance, including the **opening balance** of a new account. **Adjustments
  (including opening balances) change balances but are never counted as income or spending.** They have
  no category, so they can't slip in through a category group.

## Signs and balances

`amount_cents` is signed from the account's point of view: **negative = money out, positive = money in**. An
account's balance is the plain sum of its transactions.

**For `credit_card` and `loan` accounts a negative balance means money owed. Charges are negative, and payments
and refunds are positive.** A card payment from checking is a linked transfer: -X on checking, +X on the card.
This makes net worth the plain sum of every account's balance. CSV import must flip card issuers that export
charges as positive numbers (the `flip_sign` choice, saved with the account's mapping;
[csv-import.md](csv-import.md)). The dashboard and phone show a negative card or loan balance as "$50.00 owed".

Worked example (fake data, also a test in `server/tests/test_accounts_api.py`):

| Account | Transaction | `amount_cents` |
| --- | --- | ---: |
| Checking | Opening balance (`adjustment`) | 200000 |
| Checking | Card payment (`transfer`, linked) | -30000 |
| Card | Charge | -12000 |
| Card | Charge | -25000 |
| Card | Refund | 2000 |
| Card | Card payment (`transfer`, linked) | 30000 |

Checking = **170000** ($1,700.00). Card = **-5000** ($50.00 owed). Sum of all balances = **165000**.

## Routes (this computer only)

- **Accounts:** `GET/POST /api/local/accounts`, `GET/PATCH/DELETE /api/local/accounts/{id}`.
  - `balance_cents` is the sum of the account's transactions; record a starting balance as an `adjustment`.
  - An account with transactions can't be deleted.
- **Transactions:** `GET/POST /api/local/transactions` (filters: `account_id`, `category_id`, `date_from`,
  `date_to`, `kind`, `q`, `limit`, `offset`; newest first), `GET/PATCH/DELETE /api/local/transactions/{id}`.
  - Send `amount_cents`, or `amount` as dollar text (`"-12.34"`).
  - Adjustments can't have a category. A `refund` must be a positive amount.

## Transfers and lock rules

- `POST/DELETE /api/local/transactions/{id}/transfer` links or unlinks a transfer between two of your accounts.
  Only two regular (`normal`) transactions can be linked; both move to the Transfer category.
- While linked, a transaction's account, amount, kind and category are locked and it can't be deleted: remove
  the link first.
- A transaction that backs a paycheck has its own locks ([paychecks.md](paychecks.md)).
- A payment sorted into charity (`donation_id` in the transaction's JSON) keeps its amount and kind, and can't be
  linked as a transfer, until the donation is removed (409 `linked_to_donation`; [donations.md](donations.md)).
