"""Manually entered transactions, filtering, and linking transfers between your own accounts."""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import (
    Category,
    CategoryGroup,
    Paycheck,
    Transaction,
    TransactionKind,
    TransactionSource,
)
from app.schemas.transactions import TransactionCreate, TransactionPage, TransactionUpdate
from app.services.accounts import get_account
from app.services.category_rules import load_matcher

# Changing these on one side of a transfer (or on a paycheck's deposit) would break the link,
# so unlink first.
_TRANSFER_LOCKED_FIELDS = {"account_id", "amount_cents", "kind"}
_DEPOSIT_LOCKED_MESSAGE = (
    "This deposit is linked to a paycheck. Remove that link before changing its account, amount, "
    "or kind, or making it part of a transfer."
)


@dataclass(frozen=True)
class TransactionFilters:
    account_id: int | None = None
    category_id: int | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    kind: TransactionKind | None = None
    search: str | None = None
    limit: int = 100
    offset: int = 0


def get_transaction(session: Session, transaction_id: int) -> Transaction:
    transaction = session.get(Transaction, transaction_id)
    if transaction is None:
        raise not_found("transaction")
    return transaction


def _check_references(session: Session, data: dict) -> None:
    if data.get("account_id") is not None:
        get_account(session, data["account_id"])
    if data.get("category_id") is not None and session.get(Category, data["category_id"]) is None:
        raise not_found("category")


def _check_kind_rules(kind: TransactionKind, amount_cents: int, category_id: int | None) -> None:
    """Rules that depend on several fields together. Run on the final values after an edit,
    since a PATCH can change the kind and the amount separately."""
    if kind == TransactionKind.REFUND and amount_cents <= 0:
        raise ApiError(
            422,
            "invalid_refund",
            "A refund is money coming back, so its amount must be positive.",
        )
    # Adjustments (including opening balances) change balances but are never income or
    # spending, so they mustn't reach the monthly summary through a category.
    if kind == TransactionKind.ADJUSTMENT and category_id is not None:
        raise ApiError(
            422,
            "invalid_category",
            "Adjustments, such as a starting balance, aren't income or spending, so they can't "
            "have a category.",
        )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_transactions(session: Session, filters: TransactionFilters) -> TransactionPage:
    """Newest first (by date, then most recently added)."""
    query = select(Transaction)
    if filters.account_id is not None:
        query = query.where(Transaction.account_id == filters.account_id)
    if filters.category_id is not None:
        query = query.where(Transaction.category_id == filters.category_id)
    if filters.date_from is not None:
        query = query.where(Transaction.date >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(Transaction.date <= filters.date_to)
    if filters.kind is not None:
        query = query.where(Transaction.kind == filters.kind)
    if filters.search:
        # SQLite's LIKE is case-insensitive for ASCII letters.
        pattern = f"%{_escape_like(filters.search)}%"
        query = query.where(Transaction.description.like(pattern, escape="\\"))

    total = session.scalar(select(func.count()).select_from(query.subquery()))
    items = session.scalars(
        query.order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(filters.limit)
        .offset(filters.offset)
    ).all()
    return TransactionPage.model_validate(
        {"items": items, "total": total, "limit": filters.limit, "offset": filters.offset}
    )


def create_transaction(session: Session, data: TransactionCreate) -> Transaction:
    values = data.model_dump(exclude={"amount"})
    if "category_id" not in data.model_fields_set and values["kind"] == TransactionKind.NORMAL:
        values["category_id"] = load_matcher(session)(values["description"])  # rules, if any
    _check_kind_rules(values["kind"], values["amount_cents"], values["category_id"])
    _check_references(session, values)
    transaction = Transaction(**values, source=TransactionSource.MANUAL)
    session.add(transaction)
    session.commit()
    return transaction


def update_transaction(
    session: Session, transaction_id: int, data: TransactionUpdate
) -> Transaction:
    transaction = get_transaction(session, transaction_id)
    changes = data.changes()
    changes.pop("amount", None)
    if transaction.transfer_pair_id is not None and (
        _TRANSFER_LOCKED_FIELDS & changes.keys()
        or ("category_id" in changes and not _is_transfer_category(session, changes["category_id"]))
    ):
        raise ApiError(
            409,
            "part_of_transfer",
            "This transaction is part of a transfer. Remove the transfer link before changing "
            "its account, amount, kind, or category.",
        )
    if _TRANSFER_LOCKED_FIELDS & changes.keys() and _is_paycheck_deposit(session, transaction):
        raise ApiError(409, "linked_to_paycheck", _DEPOSIT_LOCKED_MESSAGE)
    _check_kind_rules(
        changes.get("kind", transaction.kind),
        changes.get("amount_cents", transaction.amount_cents),
        changes.get("category_id", transaction.category_id),
    )
    _check_references(session, changes)
    for field, value in changes.items():
        setattr(transaction, field, value)
    session.commit()
    return transaction


def _is_paycheck_deposit(session: Session, transaction: Transaction) -> bool:
    query = select(Paycheck.id).where(Paycheck.deposit_transaction_id == transaction.id)
    return session.scalar(query) is not None


def _is_transfer_category(session: Session, category_id: int | None) -> bool:
    category = session.get(Category, category_id) if category_id is not None else None
    return category is not None and category.group == CategoryGroup.TRANSFER


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


def delete_transaction(session: Session, transaction_id: int) -> None:
    """Delete it. Half of a transfer can't be deleted until the link is removed.

    Otherwise the other half would quietly turn into spending or income.
    """
    transaction = get_transaction(session, transaction_id)
    if transaction.transfer_pair_id is not None:
        raise ApiError(
            409,
            "part_of_transfer",
            "This transaction is part of a transfer. Remove the transfer link before deleting "
            "this transaction.",
        )
    session.delete(transaction)
    session.commit()


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
    if _is_paycheck_deposit(session, first) or _is_paycheck_deposit(session, second):
        raise ApiError(409, "linked_to_paycheck", _DEPOSIT_LOCKED_MESSAGE)
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
    first.transfer_pair_id, second.transfer_pair_id = second.id, first.id
    first.kind = second.kind = TransactionKind.TRANSFER
    # So a category filter (e.g. Groceries) doesn't list money you only moved.
    first.category_id = second.category_id = _transfer_category_id(session)
    session.commit()
    return first


def unlink_transfer(session: Session, transaction_id: int) -> Transaction:
    """Undo a transfer link. Both sides go back to being normal transactions.

    They keep the Transfer category, so they still don't count as spending or income until the
    user picks another category.
    """
    transaction = get_transaction(session, transaction_id)
    if transaction.transfer_pair_id is None:
        raise ApiError(409, "not_a_transfer", "This transaction isn't linked as a transfer.")
    _unlink(transaction, session.get(Transaction, transaction.transfer_pair_id))
    session.commit()
    return transaction
