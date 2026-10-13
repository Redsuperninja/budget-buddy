"""Dividends: the yearly list and totals, and "not a dividend". Finding them is in
``dividend_matching``; which ones the monthly summary leaves out is in ``transaction_roles``."""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models import Account, Category, Dividend, Transaction, TransactionKind
from app.schemas.dividends import DividendOut, DividendsOut
from app.services.accounts import TAX_FREE_KINDS
from app.services.dividend_matching import CATEGORY


def list_dividends(session: Session, tax_year: int) -> DividendsOut:
    """A dividend counts in the year it was paid (its transaction's date)."""
    rows = session.execute(
        select(Dividend, Transaction, Account.kind)
        .join(Transaction, Transaction.id == Dividend.transaction_id)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Dividend.dismissed.is_(False),
            # Still a dividend: a payment later changed to money out or a transfer doesn't count.
            Transaction.amount_cents > 0,
            Transaction.kind == TransactionKind.NORMAL,
            Transaction.date.between(dt.date(tax_year, 1, 1), dt.date(tax_year, 12, 31)),
        )
        .order_by(Transaction.date, Transaction.id)
    ).all()
    dividends = [
        DividendOut(
            id=d.id,
            transaction_id=t.id,
            sweep_transaction_id=d.sweep_transaction_id,
            account_id=t.account_id,
            payer=d.payer,
            paid_on=t.date,
            amount_cents=t.amount_cents,
            taxed=kind not in TAX_FREE_KINDS,
        )
        for d, t, kind in rows
    ]
    return DividendsOut(
        tax_year=tax_year,
        dividends=dividends,
        total_cents=sum(d.amount_cents for d in dividends),
        taxed_cents=sum(d.amount_cents for d in dividends if d.taxed),
    )


def dismiss(session: Session, dividend_id: int) -> None:
    """Not a dividend: drop it from lists and totals, free its sweep, and take the payment out of
    "Dividends" if Budget Buddy put it there. It's remembered, so it isn't found again."""
    dividend = session.get(Dividend, dividend_id)
    if dividend is None or dividend.dismissed:
        raise not_found("dividend")
    payment = session.get(Transaction, dividend.transaction_id)
    category = session.get(Category, payment.category_id) if payment.category_id else None
    if category and category.name == CATEGORY and payment.category_source is None:
        payment.category_id = None
    dividend.dismissed = True
    dividend.sweep_transaction_id = None
    session.commit()
