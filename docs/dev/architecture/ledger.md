# Accounts and transactions (the ledger)

Code: `services/ledger/accounts.py`, `services/ledger/transactions.py`, `services/ledger/transaction_roles.py`, `routers/ledger/accounts.py`,
`routers/ledger/transactions.py`.
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

## Transaction roles

Besides its kind and category, a transaction can be **used as** something, recorded by a link from another
table: a paycheck's deposit, a donation, a stock purchase or sale, a trade or dividend found in a bank file, or
the deposit sweep next to one. `services/ledger/transaction_roles.py` is the one place that knows those links. Each
role is a select of transaction ids, and `none_of(...)` turns roles into conditions (one `NOT IN` each, since
SQLite can't nest one `UNION` inside another). The monthly summary, "needs a category", transfer matching,
sweep and trade finding, repeat gifts and pay deposits all leave roles out through it, so a new role is added
there once. Two groups are named: `cash_inside_account()` (stock trades, bank-file trades and their sweeps:
never spending, income or a transfer) and `dividends_kept_inside()` (a dividend in a retirement account or HSA,
and its sweep). A dismissed dividend or bank trade loses its sweep, so a linked sweep always belongs to one
that's shown.

## Signs and balances

`amount_cents` is signed from the account's point of view: **negative = money out, positive = money in**. An
account's balance is the plain sum of its transactions. The accounts API gives both `balance_cents` (every
transaction) and `current_balance_cents` (only those dated today or earlier, this computer's calendar), so a bill
entered ahead of time doesn't lower today's balance; the dashboard's balances and net worth, and the phone
snapshot, use today's.

**For `credit_card` and `loan` accounts a negative balance means money owed. Charges are negative, and payments
and refunds are positive.** A card payment from checking is a linked transfer: -X on checking, +X on the card.
This makes net worth the plain sum of every account's balance. CSV import must flip card issuers that export
charges as positive numbers (the `flip_sign` choice, saved with the account's mapping, and noticed by itself for
card accounts; [csv-import.md](csv-import.md)). The dashboard and phone show a negative card or loan balance as "$50.00 owed", and a positive one (overpaid) as "$12.00 credit".

Worked example (fake data, also a test in `server/tests/ledger/test_accounts_api.py`):

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

- **Match everything again:** `POST /api/local/transactions/match-again` (`services/ledger/match_again.py`), in one savepoint,
  picks every sweep link again (they're all automatic; a link the new pick leaves free is put back, so it only adds)
  and runs the finders over all transactions: dividends, stock trades (and
  recorded trades with a sweep nearby), sweeps one each then several at once, transfers. Dismissed dividends and
  trades, transfer links and `auto_transfer_off`, categories and recorded shares are kept. Returns
  `{dividends_found, trades_found, sweeps_linked, transfers_linked}`.

- **Accounts:** `GET/POST /api/local/accounts`, `GET/PATCH/DELETE /api/local/accounts/{id}`.
  - `retirement_type` (`roth_ira`, `traditional_ira`, `401k`, `roth_401k`, `403b`, `other`) only on a `retirement`
    account (422 otherwise); changing the kind away from retirement clears it.
  - `balance_cents` is the sum of the account's transactions; record a starting balance as an `adjustment`.
    `current_balance_cents` counts only those dated today or earlier (what Home and the Accounts list show).
  - An account with transactions can't be deleted.
  - `POST /api/local/accounts/{id}/balance` `{date, balance_cents | balance}`: the bank's balance at the end of
    `date` (today or earlier). Adds one `adjustment` dated `date` for the difference from the sum of the account's
    transactions up to that day; nothing when it already matches. Returns `adjustment_cents`, `transaction_id`
    and `balance_now_cents` (end of today; an older day's change moves it too) (`services/ledger/account_balance.py`).
    It equals the account's `current_balance_cents`; `balance_cents` also includes future-dated transactions.
- **Transactions:** `GET/POST /api/local/transactions` (filters: `account_id`, `category_id`, `date_from`,
  `date_to`, `kind`, `q`, `sorted_by` (`rule` or `you`, [category-rules.md](category-rules.md)), `uncategorized` (`true`: normal and
  refund transactions with no category yet; transfers and adjustments never need one), `hide_dividends`
  ([dividends.md](dividends.md)), `hide_adjustments` (leave out balance adjustments), `limit`, `offset`;
  newest first), `GET/PATCH/DELETE /api/local/transactions/{id}`.
  - Send `amount_cents`, or `amount` as dollar text (`"-12.34"`).
  - Adjustments can't have a category. A `refund` must be a positive amount.

## Transfers and lock rules

- `POST/DELETE /api/local/transactions/{id}/transfer` links or unlinks a transfer between two of your accounts.
  Only two regular (`normal`) transactions can be linked; both move to the Transfer category. Most pairs are
  linked automatically, and each linked side has a `transfer_type` ([transfers.md](transfers.md)).
- While linked, a transaction's account, amount, kind and category are locked and it can't be deleted: remove
  the link first.
- A transaction that backs a paycheck has its own locks ([paychecks.md](paychecks.md)).
- `POST /api/local/transactions/{id}/personal-gift` files a payment under "Gifts" ([donations.md](donations.md)).
- A payment sorted into charity (`donation_id` in the transaction's JSON) keeps its amount and kind, and can't be
  linked as a transfer, until the donation is removed (409 `linked_to_donation`; [donations.md](donations.md)).
