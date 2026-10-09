"""Transfers between your own accounts: linking two transactions as one transfer, undoing it,
and what kind of transfer it is (a card payment, money into savings...). Matching them up
automatically is in ``transfer_matching``.

A transfer is two regular transactions on different accounts, one out and one in, for the same
amount. Linked, both become kind "transfer" in the transfer group's category, so they're never
counted as income or spending; money into savings-type accounts counts as saved
(``savings_transfers``).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Category, CategoryGroup, Transaction, TransactionKind
from app.services.transactions import (
    _DEPOSIT_LOCKED_MESSAGE,
    _DONATION_LOCKED_MESSAGE,
    get_transaction,
    is_paycheck_deposit,
)


def _transfer_category_id(session: Session) -> int | None:
    """The starter "Transfer" category (or another in the transfer group), if there is one."""
    return session.scalar(
        select(Category.id)
        .where(Category.group == CategoryGroup.TRANSFER)
        .order_by((Category.name == "Transfer").desc(), Category.id)
        .limit(1)
    )


def _unlink(transaction: Transaction, partner: Transaction | None) -> None:
    for side in (transaction, partner):
        if side is not None:
            side.transfer_pair_id = None
            side.kind = TransactionKind.NORMAL
            side.auto_transfer_off = True


def link_transfer(session: Session, transaction_id: int, other_id: int) -> Transaction:
    """Mark two transactions as one transfer between your own accounts.

    They must be regular (kind "normal") transactions on different accounts, with opposite signs
    and the same size, e.g. -$500.00 out of checking and +$500.00 into savings. Both become kind
    "transfer", move to the Transfer category, and point at each other.
    """
    first = get_transaction(session, transaction_id)
    second = get_transaction(session, other_id)
    if first.id == second.id:
        raise ApiError(422, "invalid_transfer", "A transfer needs two different transactions.")
    if first.transfer_pair_id == second.id and second.transfer_pair_id == first.id:
        return first  # already linked
    if first.transfer_pair_id is not None or second.transfer_pair_id is not None:
        raise ApiError(
            409,
            "already_linked",
            "One of these transactions is already part of another transfer. "
            "Remove that link first.",
        )
    if is_paycheck_deposit(session, first) or is_paycheck_deposit(session, second):
        raise ApiError(409, "linked_to_paycheck", _DEPOSIT_LOCKED_MESSAGE)
    if first.donation is not None or second.donation is not None:
        raise ApiError(409, "linked_to_donation", _DONATION_LOCKED_MESSAGE)
    if first.kind != TransactionKind.NORMAL or second.kind != TransactionKind.NORMAL:
        # Linking would hide what a refund or an opening-balance adjustment was, and unlinking
        # couldn't bring it back.
        raise ApiError(
            422, "invalid_transfer", "Only regular transactions can be linked as a transfer."
        )
    if first.account_id == second.account_id:
        raise ApiError(
            422, "invalid_transfer", "A transfer has to be between two different accounts."
        )
    if first.amount_cents == 0 or first.amount_cents != -second.amount_cents:
        raise ApiError(
            422,
            "invalid_transfer",
            "A transfer needs one amount going out and the same amount coming in.",
        )
    pair_up(session, first, second)
    session.commit()
    return first


def pair_up(session: Session, first: Transaction, second: Transaction) -> None:
    """Link two checked transactions as one transfer (the caller commits)."""
    first.transfer_pair_id, second.transfer_pair_id = second.id, first.id
    for side in (first, second):
        side.kind = TransactionKind.TRANSFER
        # So a category filter (e.g. Groceries) doesn't list money you only moved. Budget Buddy's
        # choice, not yours or a rule's.
        side.category_id = _transfer_category_id(session)
        side.category_source = side.sorted_by_rule_id = None
        side.auto_transfer_off = False
    session.flush()
    session.expire(first, ["transfer_partner"])
    session.expire(second, ["transfer_partner"])


def unlink_transfer(session: Session, transaction_id: int) -> Transaction:
    """Undo a transfer link. Both sides go back to being normal transactions.

    They keep the Transfer category, so they still don't count as spending or income until the
    user picks another category. Automatic matching won't link either of them again.
    """
    transaction = get_transaction(session, transaction_id)
    if transaction.transfer_pair_id is None:
        raise ApiError(409, "not_a_transfer", "This transaction isn't linked as a transfer.")
    _unlink(transaction, session.get(Transaction, transaction.transfer_pair_id))
    session.commit()
    return transaction
