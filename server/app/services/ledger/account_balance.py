"""Setting an account's balance to what the bank says (roadmap 5c).

You say "on this date, the balance was X" (today's balance from the bank, or the balance at the
start of the year). Budget Buddy adds up the account's transactions dated on or before that day and
records the difference as one balance adjustment on that day. Adjustments change balances but are
never income or spending (docs/dev/architecture/ledger.md). Setting it again adds another
adjustment for whatever difference is left, so the total always comes out right.

For credit cards and loans the balance is what you owe, sent as a negative amount (the dashboard
asks for "amount owed" and flips the sign).
"""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Transaction, TransactionKind, TransactionSource
from app.money import cents_to_display
from app.schemas.ledger.accounts import BalanceSet, BalanceSetResult
from app.services.ledger.accounts import get_account


def balance_on(session: Session, account_id: int, day: dt.date) -> int:
    """The account's balance at the end of ``day``: every transaction dated on or before it."""
    return int(
        session.scalar(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                Transaction.account_id == account_id, Transaction.date <= day
            )
        )
        or 0
    )


def set_balance(session: Session, account_id: int, data: BalanceSet) -> BalanceSetResult:
    get_account(session, account_id)
    before = balance_on(session, account_id, data.date)
    difference = data.balance_cents - before
    adjustment = None
    if difference:
        adjustment = Transaction(
            account_id=account_id,
            date=data.date,
            amount_cents=difference,
            description=(
                f"Balance set to {cents_to_display(data.balance_cents)} on {data.date.isoformat()}"
            ),
            kind=TransactionKind.ADJUSTMENT,
            source=TransactionSource.MANUAL,
        )
        session.add(adjustment)
        session.commit()
    return BalanceSetResult(
        date=data.date,
        balance_cents=data.balance_cents,
        adjustment_cents=difference,
        transaction_id=adjustment.id if adjustment else None,
        balance_now_cents=balance_on(session, account_id, dt.date.today()),
    )
