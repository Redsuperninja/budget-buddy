"""Filing gifts under a category: a payment sorted into charity goes in "Charitable giving", a
personal gift (a birthday present, say) in "Gifts". Both are spending in the wants group, made the
first time they're needed. A personal gift is only a category: it isn't a tax record.

The categories are found by name (ignoring upper and lower case), so renaming one means Budget
Buddy makes a fresh one next time. A same-named category in the income or transfer group is never
used for spending: a charity gift then keeps its category (the tax record matters more), and a
personal gift is refused with a message saying how to fix it.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import (
    Category,
    CategoryGroup,
    CategorySource,
    Donation,
    Transaction,
    TransactionKind,
)
from app.services.transactions import get_transaction

CHARITY = "Charitable giving"
PERSONAL = "Gifts"
_SPENDING_GROUPS = {CategoryGroup.NEEDS, CategoryGroup.WANTS, CategoryGroup.SAVINGS}


def _category_id(session: Session, name: str) -> int | None:
    """The spending category called ``name``, made in the wants group if there isn't one. None if
    the name is taken by an income or transfer category (names are unique)."""
    wanted = name.casefold()
    matches = [c for c in session.scalars(select(Category)) if c.name.casefold() == wanted]
    spending = [c for c in matches if c.group in _SPENDING_GROUPS]
    if spending:
        return spending[0].id
    if matches:
        return None
    category = Category(name=name, group=CategoryGroup.WANTS, budget_cents=0)
    session.add(category)
    session.flush()
    return category.id


def file_under(session: Session, payment: Transaction, name: str) -> bool:
    """Put the payment in the gift category ``name`` (not saved until the caller commits). False
    if that name belongs to an income or transfer category, so the payment was left as it was."""
    category_id = _category_id(session, name)
    if category_id is None:
        return False
    payment.category_id = category_id
    payment.category_source = CategorySource.YOU.value  # a choice you made, not a rule
    payment.sorted_by_rule_id = None
    return True


def mark_personal_gift(session: Session, transaction_id: int) -> Transaction:
    """File a payment under "Gifts": a present for someone, not a gift to charity."""
    payment = get_transaction(session, transaction_id)
    if payment.kind != TransactionKind.NORMAL or payment.amount_cents >= 0:
        raise ApiError(422, "invalid_payment", "Only money you paid out can be marked as a gift.")
    if session.scalar(select(Donation.id).where(Donation.transaction_id == payment.id)):
        raise ApiError(
            409,
            "linked_to_donation",
            "This payment is already a gift to charity. Remove it on the Donations page first.",
        )
    if not file_under(session, payment, PERSONAL):
        raise ApiError(
            409,
            "name_taken",
            f'You have an income or transfer category called "{PERSONAL}", so presents '
            "can't be filed there. Rename that category on the Categories page, then try again.",
        )
    session.commit()
    return payment
