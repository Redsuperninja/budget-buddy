"""Sorting a transaction into charity: the rules for linking a gift to the payment it came from.

A linked gift must be a cash gift (money from a bank or card) paid by a regular money-out
transaction, at most the size of that payment (the rest may have bought something, like a
fundraiser dinner), and one payment backs at most one gift. Checked on the final values, since a
PATCH can change the kind, the amount, or the link separately.

The gift's date is its own fact, not the payment's: a bank may show the day a check cleared, but a
gift counts on the day the check was mailed or the card was charged (IRS Publication 526).
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Donation, DonationKind, Transaction, TransactionKind
from app.money import cents_to_display
from app.schemas.donations import ProofItem
from app.services.gift_categories import CHARITY, file_under
from app.services.ledger.transactions import get_transaction

_ALREADY_LINKED = "That payment is already recorded as a donation."


def check_payment(
    session: Session,
    transaction_id: int | None,
    kind: DonationKind,
    amount_cents: int,
    donation_id: int | None = None,
) -> None:
    """Raise if the gift (``donation_id``, None for a new one) can't be linked to the payment."""
    if transaction_id is None:
        return
    payment = get_transaction(session, transaction_id)
    other = session.scalar(select(Donation.id).where(Donation.transaction_id == payment.id))
    if other is not None and other != donation_id:
        raise ApiError(409, "already_linked", _ALREADY_LINKED)
    if payment.kind != TransactionKind.NORMAL or payment.amount_cents >= 0:
        raise ApiError(
            422,
            "invalid_payment",
            "Only money you paid out can be a donation. Transfers, refunds, money coming in, and "
            "balance adjustments can't.",
        )
    if kind != DonationKind.CASH:
        raise ApiError(
            422,
            "invalid_payment",
            "A payment from your bank or card is a cash gift. Set the type to cash, or remove "
            "the link to the payment for a gift of goods.",
        )
    if amount_cents > -payment.amount_cents:
        raise ApiError(
            422,
            "invalid_payment",
            "The gift can't be more than the payment it came from.",
        )


def file_new_link(session: Session, transaction_id: int | None, previous_id: int | None) -> None:
    """A payment newly sorted into charity goes in the "Charitable giving" category."""
    if transaction_id is not None and transaction_id != previous_id:
        file_under(session, get_transaction(session, transaction_id), CHARITY)


def commit(session: Session) -> None:
    """Save, turning a second link to the same payment made at the same moment into a 409."""
    try:
        session.commit()
    except IntegrityError:  # two saves of the same payment at once (the unique index caught it)
        session.rollback()
        raise ApiError(409, "already_linked", _ALREADY_LINKED) from None


def payment_amounts(session: Session, donations: Iterable[Donation]) -> dict[int, int]:
    """Payment size (positive cents) by transaction ID, for the gifts that came from a payment."""
    ids = [d.transaction_id for d in donations if d.transaction_id is not None]
    if not ids:
        return {}
    rows = session.execute(
        select(Transaction.id, Transaction.amount_cents).where(Transaction.id.in_(ids))
    )
    return {row_id: -amount for row_id, amount in rows}


def part_gift_proof(gift_cents: int, payment_cents: int | None) -> list[ProofItem]:
    """When only part of a payment was a gift (you got something back, like a dinner), a bank record
    shows the payment, not the gift, so keep the charity's statement of what you received."""
    if payment_cents is None or gift_cents >= payment_cents:
        return []
    return [
        ProofItem(
            code="quid_pro_quo_statement",
            message=(
                f"You paid {cents_to_display(payment_cents)} and got something back, so only "
                f"{cents_to_display(gift_cents)} is a gift. Keep the charity's statement showing "
                "what you received and about what it was worth. A bank record alone doesn't show "
                "this."
            ),
        )
    ]
