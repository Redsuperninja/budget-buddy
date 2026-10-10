"""Filing gifts under a category: a payment sorted into charity goes in "Charitable giving", a
personal gift (a birthday present, say) in "Gifts". Both are spending in the wants group, made the
first time they're needed. A personal gift is only a category: it isn't a tax record.

They're found or made by name (``named_categories``). A same-named category in the income or
transfer group is never used for spending: a charity gift then keeps its category (the tax record
matters more), and a personal gift is refused with a message saying how to fix it.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import (
    CategoryGroup,
    CategorySource,
    Donation,
    Transaction,
    TransactionKind,
)
from app.services.named_categories import find_or_make
from app.services.transactions import get_transaction

CHARITY = "Charitable giving"
PERSONAL = "Gifts"
_SPENDING_GROUPS = {CategoryGroup.NEEDS, CategoryGroup.WANTS, CategoryGroup.SAVINGS}


def file_under(session: Session, payment: Transaction, name: str, by_you: bool = True) -> bool:
    """Put the payment in the gift category ``name`` (not saved until the caller commits). False
    if that name belongs to an income or transfer category, so the payment was left as it was.
    ``by_you=False`` when Budget Buddy chose it (a repeat gift), so learning doesn't count it."""
    category_id = find_or_make(session, name, _SPENDING_GROUPS, CategoryGroup.WANTS)
    if category_id is None:
        return False
    payment.category_id = category_id
    payment.category_source = CategorySource.YOU.value if by_you else None
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
