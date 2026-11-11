"""A loan payment split into principal and interest (ADR-0017 decision 5, roadmap 10f-4).

A split transaction on a bank account whose one Transfer-group part equals a deposit on a loan
account is linked to that deposit through the ordinary manual transfer link. Both sides get
``transfer_pair_id``; the loan side becomes a transfer as usual, while the split side stays
"normal" so its other parts (interest, escrow) still count as spending. Its Transfer part is
ignored like any transfer-group line (``category_lines``), and the principal is never "saved".
While linked, the split is locked like a transfer: undo or replace it only after unlinking.
Matching is never automatic for a split (``transaction_roles.free_to_move``).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import AccountKind, Category, CategoryGroup, Transaction, TransactionKind
from app.services.ledger.savings_transfers import SAVINGS_KINDS
from app.services.ledger.transaction_roles import refuse_if_split
from app.services.ledger.transfer_categories import pair_category

LINKED_SPLIT_MESSAGE = (
    "This split is linked to a loan account's payment. Remove the transfer link first to change "
    "or undo the split."
)


def _invalid(message: str) -> ApiError:
    return ApiError(422, "invalid_transfer", message)


def link_split_to_loan(session: Session, first: Transaction, second: Transaction) -> None:
    """Link a split (money out of a bank account) to a loan deposit equal to its Transfer part.
    The caller has checked that both are regular, unlinked and on different accounts, and
    commits."""
    split, other = (first, second) if first.splits else (second, first)
    if other.account.kind != AccountKind.LOAN:
        # Only a loan can take a split's principal; anything else keeps 10f-3's refusal.
        refuse_if_split(split, "make it part of a transfer")
    if split.account.kind == AccountKind.LOAN or split.amount_cents >= 0 or other.amount_cents <= 0:
        raise _invalid("A split loan payment goes out of a bank account into a loan account.")
    if split.account.kind in SAVINGS_KINDS:
        # The split side stays "normal", so a savings-type account would overstate what was saved.
        raise _invalid(
            "A split loan payment must go out of an everyday bank account or card, not a savings, "
            "brokerage, retirement or HSA account."
        )
    in_transfer_group = set(
        session.scalars(select(Category.id).where(Category.group == CategoryGroup.TRANSFER))
    )
    parts = [p for p in split.splits if p.category_id in in_transfer_group]
    if len(parts) != 1:
        raise _invalid(
            "To link a split to a loan, exactly one of its parts must be in the Transfer category."
        )
    if -parts[0].amount_cents != other.amount_cents:
        raise _invalid("The split's Transfer part must equal the loan payment's amount exactly.")
    split.transfer_pair_id, other.transfer_pair_id = other.id, split.id
    # The loan side moves to Transfer and is remembered for an unlink; the split keeps its parts.
    other.pre_transfer_category_id = other.category_id
    other.pre_transfer_category_source = other.category_source
    other.pre_transfer_rule_id = other.sorted_by_rule_id
    other.kind = TransactionKind.TRANSFER
    other.category_id = pair_category(session, split, other)
    other.category_source = other.sorted_by_rule_id = None
    other.auto_transfer_off = split.auto_transfer_off = False
    session.flush()
    session.expire(split, ["transfer_partner"])
    session.expire(other, ["transfer_partner"])
