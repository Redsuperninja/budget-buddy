"""Filing gifts under a category: a payment sorted into charity goes in "Charitable giving", a
personal gift (a birthday present, say) in "Gifts". Both are spending in the wants group, made the
first time they're needed. A personal gift is only a category: it isn't a tax record.

The categories are found by name (ignoring upper and lower case), so renaming one means Budget
Buddy makes a fresh one next time. A same-named category in the income or transfer group is never
used for spending; the payment then keeps its category.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Category, CategoryGroup, Donation, Transaction, TransactionKind
from app.services.transactions import get_transaction

CHARITY = "Charitable giving"
PERSONAL = "Gifts"
_SPENDING_GROUPS = {CategoryGroup.NEEDS, CategoryGroup.WANTS, CategoryGroup.SAVINGS}


def _category_id(session: Session, name: str) -> int | None:
    """The spending category called ``name``, made in the wants group if there isn't one."""
    wanted = name.casefold()
    for category in session.scalars(select(Category)):
        if category.name.casefold() == wanted:
            return category.id if category.group in _SPENDING_GROUPS else None
    category = Category(name=name, group=CategoryGroup.WANTS, budget_cents=0)
    session.add(category)
    session.flush()
    return category.id


def file_under(session: Session, payment: Transaction, name: str) -> None:
    """Put the payment in the gift category ``name`` (not saved until the caller commits)."""
    category_id = _category_id(session, name)
    if category_id is not None:
        payment.category_id = category_id


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
    file_under(session, payment, PERSONAL)
    session.commit()
    return payment
