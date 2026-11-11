"""Split a transaction into parts, each in its own category (ADR-0017).

One function replaces the whole list. The rules live here because SQLite can't check that parts
add up: 2 to 20 parts, each nonzero with the transaction's sign, summing to its amount exactly,
on a regular payment or refund that isn't a transfer, pay deposit, donation, stock trade, dividend
or bank trade. A split transaction's own category is cleared; changing its category or amount
afterwards is refused in ``update_transaction``.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Category, Transaction, TransactionKind, TransactionSplit
from app.schemas.ledger.transactions import SplitPart
from app.services.ledger.split_loans import LINKED_SPLIT_MESSAGE
from app.services.ledger.transaction_roles import (
    bank_trade_sweeps,
    bank_trades,
    dividend_sweeps,
    dividends,
)
from app.services.ledger.transactions import get_transaction, is_paycheck_deposit, is_stock_trade

MIN_PARTS = 2
MAX_PARTS = 20


def _invalid(message: str) -> ApiError:
    return ApiError(422, "invalid_split", message)


def _refuse(message: str) -> ApiError:
    return ApiError(409, "cannot_split", message)


def _has_role(session: Session, role, transaction_id: int) -> bool:
    query = select(Transaction.id).where(Transaction.id == transaction_id, Transaction.id.in_(role))
    return session.scalar(query) is not None


def _check_can_split(session: Session, transaction: Transaction) -> None:
    if transaction.kind not in (TransactionKind.NORMAL, TransactionKind.REFUND):
        raise _refuse(
            "Only a regular payment or refund can be split, not a transfer or adjustment."
        )
    if transaction.transfer_pair_id is not None:
        raise _refuse("This transaction is part of a transfer. Remove the transfer link first.")
    reason = None
    if is_paycheck_deposit(session, transaction):
        reason = "linked to a paycheck"
    elif transaction.donation is not None:
        reason = "recorded as a donation"
    elif is_stock_trade(session, transaction):
        reason = "recorded as a stock trade"
    elif any(
        _has_role(session, role, transaction.id)
        for role in (
            dividends(include_dismissed=True),
            dividend_sweeps(),
            bank_trades(include_dismissed=True),
            bank_trade_sweeps(),
        )
    ):
        reason = "a dividend or a stock trade from a bank file"
    if reason:
        raise _refuse(f"This transaction is {reason}, so it can't be split.")


def _check_parts(session: Session, transaction: Transaction, parts: Sequence[SplitPart]) -> None:
    if not MIN_PARTS <= len(parts) <= MAX_PARTS:
        raise _invalid(f"A split has {MIN_PARTS} to {MAX_PARTS} parts.")
    negative = transaction.amount_cents < 0
    for part in parts:
        if part.amount_cents == 0 or (part.amount_cents < 0) != negative:
            raise _invalid(
                "Each part must be more than zero and go the same way as the transaction "
                "(money out, or money in)."
            )
    if sum(part.amount_cents for part in parts) != transaction.amount_cents:
        raise _invalid("The parts must add up to the transaction's amount exactly.")
    wanted = {part.category_id for part in parts}
    found = set(session.scalars(select(Category.id).where(Category.id.in_(wanted))))
    if wanted != found:
        raise not_found("category")


def replace_splits(
    session: Session, transaction_id: int, parts: Sequence[SplitPart]
) -> Transaction:
    """Make ``parts`` the transaction's split. An empty list undoes the split (it then has no
    category)."""
    transaction = get_transaction(session, transaction_id)
    if not parts and not transaction.splits:
        return transaction  # nothing to undo: leave its category and kind alone
    if transaction.splits and transaction.transfer_pair_id is not None:
        raise ApiError(409, "part_of_transfer", LINKED_SPLIT_MESSAGE)  # loan payment (10f-4)
    if parts:
        _check_can_split(session, transaction)
        _check_parts(session, transaction, parts)
    transaction.splits = [
        TransactionSplit(category_id=p.category_id, amount_cents=p.amount_cents, note=p.note)
        for p in parts
    ]
    # Split: the transaction's own category is unused. Undone: it starts with none.
    transaction.category_id = None
    transaction.category_source = None
    transaction.sorted_by_rule_id = None
    session.commit()
    return transaction
