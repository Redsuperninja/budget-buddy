"""Which category a linked transfer goes in: "Payments" for a credit card payment (the money goes
into a card, ``transfer_types``), otherwise the starter "Transfer". Both are in the transfer group,
so neither counts as spending or income. "Payments" is made the first time it's needed; if you have
a "Payments" category in another group, it's never used and card payments go in "Transfer".
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, CategoryGroup, Transaction
from app.services.budget.named_categories import find_or_make
from app.transfer_types import TransferType, classify

PAYMENTS = "Payments"


def transfer_category_id(session: Session) -> int | None:
    """The starter "Transfer" category (or another in the transfer group, never "Payments"), if
    there is one."""
    return session.scalar(
        select(Category.id)
        .where(Category.group == CategoryGroup.TRANSFER, Category.name != PAYMENTS)
        .order_by((Category.name == "Transfer").desc(), Category.id)
        .limit(1)
    )


def payments_category(session: Session) -> int | None:
    """The "Payments" category in the transfer group (made the first time; not saved until the
    caller commits), or None if that name is taken by a category in another group."""
    return find_or_make(session, PAYMENTS, {CategoryGroup.TRANSFER}, CategoryGroup.TRANSFER)


def is_card_payment(first: Transaction, second: Transaction) -> bool:
    """Two sides of a transfer whose money goes into a credit card."""
    out, into = (first, second) if first.amount_cents < 0 else (second, first)
    return classify(out.account.kind, into.account.kind) == TransferType.CARD_PAYMENT


def pair_category(
    session: Session, first: Transaction, second: Transaction, known: dict | None = None
) -> int | None:
    """The category both sides of a newly linked transfer go in. ``known``: a dict kept for one
    matching run, so the two categories are looked up once, not once per pair."""
    known = {} if known is None else known
    if is_card_payment(first, second):
        if "payments" not in known:
            known["payments"] = payments_category(session)
        if known["payments"] is not None:
            return known["payments"]
    if "transfer" not in known:
        known["transfer"] = transfer_category_id(session)
    return known["transfer"]
