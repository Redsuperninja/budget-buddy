"""Accounts and their balances.

Balance = the sum of every transaction on the account (transfers included, since they really
move money). The ``accounts`` table has no opening-balance column, so a starting balance is
recorded as an ``adjustment`` transaction. ``current_balance_cents`` counts only transactions
dated today or earlier (this computer's calendar), so a bill entered ahead of time for next week
doesn't lower today's balance yet; ``balance_cents`` counts them all.
"""

import datetime as dt

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Account, AccountKind, StockLot, StockSaleOrder, Transaction
from app.schemas.ledger.accounts import RETIREMENT_ONLY, AccountCreate, AccountOut, AccountUpdate

# Selling inside these accounts isn't taxed: their stock sales are left out of the gains summary.
TAX_FREE_KINDS = {AccountKind.RETIREMENT, AccountKind.HSA}
# Accounts that hold stocks and funds: a stock trade or a short "div" there means what it says.
INVESTMENT_KINDS = {AccountKind.BROKERAGE, AccountKind.RETIREMENT, AccountKind.HSA}


def _totals(session: Session, account_ids: list[int]) -> dict[int, tuple[int, int, int]]:
    """``{account_id: (balance_cents, current_balance_cents, transaction_count)}`` in one query."""
    today = dt.date.today()
    rows = session.execute(
        select(
            Transaction.account_id,
            func.coalesce(func.sum(Transaction.amount_cents), 0),
            func.coalesce(
                func.sum(case((Transaction.date <= today, Transaction.amount_cents), else_=0)), 0
            ),
            func.count(Transaction.id),
        )
        .where(Transaction.account_id.in_(account_ids))
        .group_by(Transaction.account_id)
    )
    return {account_id: (balance, now, count) for account_id, balance, now, count in rows}


def _out(account: Account, totals: dict[int, tuple[int, int, int]]) -> AccountOut:
    balance, current, count = totals.get(account.id, (0, 0, 0))
    return AccountOut.model_validate(
        {
            **_columns(account),
            "balance_cents": balance,
            "current_balance_cents": current,
            "transaction_count": count,
        }
    )


def _columns(account: Account) -> dict:
    return {c.key: getattr(account, c.key) for c in Account.__table__.columns}


def get_account(session: Session, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise not_found("account")
    return account


def list_accounts(session: Session) -> list[AccountOut]:
    accounts = session.scalars(select(Account).order_by(Account.name, Account.id)).all()
    totals = _totals(session, [a.id for a in accounts])
    return [_out(a, totals) for a in accounts]


def account_out(session: Session, account_id: int) -> AccountOut:
    return _out(get_account(session, account_id), _totals(session, [account_id]))


def create_account(session: Session, data: AccountCreate) -> AccountOut:
    account = Account(**data.model_dump())
    session.add(account)
    session.commit()
    return account_out(session, account.id)


def _has_stocks(session: Session, account_id: int) -> bool:
    return bool(
        session.scalar(select(StockLot.id).where(StockLot.account_id == account_id).limit(1))
        or session.scalar(
            select(StockSaleOrder.id).where(StockSaleOrder.account_id == account_id).limit(1)
        )
    )


def update_account(session: Session, account_id: int, data: AccountUpdate) -> AccountOut:
    account = get_account(session, account_id)
    changes = data.changes()
    kind = changes.get("kind", account.kind)
    if kind != AccountKind.RETIREMENT:
        if changes.get("retirement_type") is not None:
            raise ApiError(422, "validation_error", RETIREMENT_ONLY)
        changes["retirement_type"] = None  # no longer a retirement account
    for field, value in changes.items():
        setattr(account, field, value)
    session.commit()
    return account_out(session, account_id)


def delete_account(session: Session, account_id: int) -> None:
    """Delete an account that has no transactions and no stock purchases or sales.

    The model has no "archived" flag, and transactions point at their account with a plain
    foreign key (no cascade), so an account with history can't be removed.
    """
    account = get_account(session, account_id)
    if _totals(session, [account_id]).get(account_id, (0, 0))[1]:
        raise ApiError(
            409,
            "account_has_transactions",
            "This account has transactions, so it can't be deleted. "
            "Delete or move its transactions first.",
        )
    # Deleting would quietly move its stock purchases and sales out of the account, which
    # changes how FIFO matches them.
    if _has_stocks(session, account_id):
        raise ApiError(
            409,
            "account_has_stocks",
            "This account has stock purchases or sales, so it can't be deleted. "
            "Delete those first.",
        )
    session.delete(account)
    session.commit()
