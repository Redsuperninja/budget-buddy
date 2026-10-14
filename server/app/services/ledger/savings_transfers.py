"""Money moved into your own savings accounts counts as saved (roadmap 10b).

A linked transfer (docs/dev/architecture/ledger.md) from an everyday account (checking, cash, a
credit card...) into a savings-type account is money set aside; a transfer back out is a
withdrawal. Moves between two savings-type accounts (savings to brokerage, say) aren't new saving,
so they don't count. Only the savings-type side of each transfer is added up, so nothing is
counted twice.
"""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models import Account, AccountKind, Transaction, TransactionKind

SAVINGS_KINDS = (
    AccountKind.SAVINGS,
    AccountKind.BROKERAGE,
    AccountKind.RETIREMENT,
    AccountKind.HSA,
)


def saved_by_transfer(session: Session, start: dt.date, end: dt.date) -> int:
    """Transfers into savings-type accounts minus transfers out, ``start`` to before ``end``."""
    partner = aliased(Transaction)
    partner_account = aliased(Account)
    return session.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0))
        .join(Account, Account.id == Transaction.account_id)
        .join(partner, partner.id == Transaction.transfer_pair_id)
        .join(partner_account, partner_account.id == partner.account_id)
        .where(
            Transaction.kind == TransactionKind.TRANSFER,
            Transaction.date >= start,
            Transaction.date < end,
            Account.kind.in_(SAVINGS_KINDS),
            partner_account.kind.not_in(SAVINGS_KINDS),
        )
    )
