"""Recurring gifts to charity: a new payment to a charity you already gave to by the same kind of
payment is filed under "Charitable giving" and recorded as a donation for you.

- "The same charity" is the payment's ``shop_key`` (the start of its description, as auto-sort
  learning uses), matched against payments you linked to a cash donation for the **whole** payment.
  A gift that was only part of its payment (a charity dinner, say) is never repeated: what you got
  back can change.
- The new donation copies the charity's name from the most recent such gift; its date is the
  payment's date and its amount the whole payment. It's marked ``auto_added`` so the Donations page
  can say so. Proof rules (a written acknowledgment from $250) apply as for any gift.
- Only payments that just came in (imported or added by hand) are looked at, so deleting an
  automatic donation is final: Budget Buddy never adds it back.
- Regular money out only: not a transfer, refund, balance adjustment, paycheck deposit, stock trade
  or a payment already linked to a donation. Nothing here logs descriptions or amounts.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Donation, DonationKind, Transaction, TransactionKind
from app.services.category_learning import shop_key
from app.services.gift_categories import CHARITY, file_under
from app.services.stock_records import trade_transaction_ids


def _charities_by_key(session: Session) -> dict[str, str]:
    """Shop key -> charity name, from your whole-payment cash gifts (newest gift wins)."""
    rows = session.execute(
        select(Transaction.description, Donation.organization)
        .join(Donation, Donation.transaction_id == Transaction.id)
        .where(
            Donation.kind == DonationKind.CASH,
            Donation.amount_cents == -Transaction.amount_cents,
        )
        .order_by(Donation.date, Donation.id)
    )
    found: dict[str, str] = {}
    for description, organization in rows:
        key = shop_key(description)
        if key is not None:
            found[key.casefold()] = organization
    return found


def _new_payments(session: Session, ids: set[int]) -> list[Transaction]:
    return list(
        session.scalars(
            select(Transaction).where(
                Transaction.id.in_(ids),
                Transaction.kind == TransactionKind.NORMAL,
                Transaction.amount_cents < 0,
                Transaction.transfer_pair_id.is_(None),
                Transaction.id.not_in(
                    select(Donation.transaction_id).where(Donation.transaction_id.is_not(None))
                ),
                Transaction.id.not_in(trade_transaction_ids()),
            )
        )
    )


def repeat_gifts(session: Session, transaction_ids: set[int]) -> int:
    """Record the payments among ``transaction_ids`` that repeat a gift to charity. Returns how
    many donations were added. Not saved until the caller commits."""
    if not transaction_ids:
        return 0
    payments = _new_payments(session, transaction_ids)
    if not payments:
        return 0
    charities = _charities_by_key(session)
    added = 0
    for payment in payments:
        key = shop_key(payment.description)
        organization = charities.get(key.casefold()) if key else None
        if organization is None:
            continue
        session.add(
            Donation(
                date=payment.date,
                organization=organization,
                amount_cents=-payment.amount_cents,
                kind=DonationKind.CASH,
                transaction_id=payment.id,
                auto_added=True,
            )
        )
        file_under(session, payment, CHARITY)
        added += 1
    session.flush()
    return added
