"""Recurring gifts to charity: a new payment to a charity you already gave to by the same kind of
payment is filed under "Charitable giving" and, for the same amount, recorded as a donation for you.

- "The same charity" is the payment's ``shop_key`` (the start of its description, as auto-sort
  learning uses), matched against payments you linked to a cash donation for the **whole** payment.
  A key that only names how you paid ("CHECK 1043", "ZELLE PAYMENT TO ...") isn't a charity, so it's
  never used (``NOT_A_PAYEE``): one charity check mustn't make the rent check a gift.
- A charity you also gave a **part** gift through (a gala dinner billed like the monthly gift) is
  left alone: what you got back can't be told apart from the gift.
- Same amount as the newest gift: a cash donation is added (the charity's name from that gift, the
  payment's date, the whole payment) and marked ``auto_added``. A different amount may be a
  membership with perks or an event, so the payment is only filed under "Charitable giving"; you add
  the gift yourself with the amount that was a gift.
- Budget Buddy's filing is marked as its own (``category_source`` None), so auto-sort learning
  doesn't take it for your choice. Proof rules (a written acknowledgment from $250) apply as for any
  gift.
- Only payments that just came in (imported or added by hand) are looked at, so deleting an
  automatic donation is final: Budget Buddy never adds it back.
- Regular money out only: not a transfer, refund, balance adjustment, paycheck deposit, stock trade
  or a payment already linked to a donation. Nothing here logs descriptions or amounts.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Donation, DonationKind, Transaction, TransactionKind
from app.services.category_learning import shop_key
from app.services.gift_categories import CHARITY, file_under
from app.services.transaction_roles import donations, none_of, stock_trades

# First words of a description that say how you paid, not who you paid.
NOT_A_PAYEE = frozenset(
    {
        "ACH", "ATM", "BILL", "CASH", "CHECK", "CHECKS", "CHK", "DEPOSIT", "E-TRANSFER", "ONLINE",
        "PAYPAL", "PMT", "TRANSFER", "VENMO", "WIRE", "WITHDRAWAL", "XFER", "ZELLE",
    }
)  # fmt: skip


@dataclass
class Repeats:
    filed: int = 0  # put in "Charitable giving"
    recorded: int = 0  # of those, added as donations (same amount as last time)


@dataclass
class _Charity:
    organization: str
    amount_cents: int  # the newest whole-payment gift
    part_gift: bool = False  # some gift through this key was only part of its payment


def _charity_key(description: str) -> str | None:
    key = shop_key(description)
    if key is None or key.split()[0].strip("*#:-").upper() in NOT_A_PAYEE:
        return None
    return key.casefold()


def _charities_by_key(session: Session) -> dict[str, _Charity]:
    """Charity key -> what you gave there before, from cash gifts linked to a payment."""
    rows = session.execute(
        select(
            Transaction.description,
            Transaction.amount_cents,
            Donation.organization,
            Donation.amount_cents,
        )
        .join(Donation, Donation.transaction_id == Transaction.id)
        .where(Donation.kind == DonationKind.CASH)
        .order_by(Donation.date, Donation.id)
    )
    found: dict[str, _Charity] = {}
    for description, paid_cents, organization, gift_cents in rows:
        key = _charity_key(description)
        if key is None:
            continue
        before = found.get(key)
        if gift_cents < -paid_cents:  # part of the payment was a gift
            found[key] = before or _Charity(organization, gift_cents)
            found[key].part_gift = True
        else:
            part = before.part_gift if before else False
            found[key] = _Charity(organization, gift_cents, part)
    return found


def _new_payments(session: Session, ids: set[int]) -> list[Transaction]:
    return list(
        session.scalars(
            select(Transaction).where(
                Transaction.id.in_(ids),
                Transaction.kind == TransactionKind.NORMAL,
                Transaction.amount_cents < 0,
                Transaction.transfer_pair_id.is_(None),
                *none_of(donations(), stock_trades()),
            )
        )
    )


def repeat_gifts(session: Session, transaction_ids: set[int]) -> Repeats:
    """File the payments among ``transaction_ids`` that repeat a gift to charity, and record the
    ones for the same amount. Not saved until the caller commits."""
    done = Repeats()
    payments = _new_payments(session, transaction_ids) if transaction_ids else []
    if not payments:
        return done
    charities = _charities_by_key(session)
    for payment in payments:
        key = _charity_key(payment.description)
        charity = charities.get(key) if key else None
        if charity is None or charity.part_gift:
            continue
        file_under(session, payment, CHARITY, by_you=False)
        done.filed += 1
        if -payment.amount_cents != charity.amount_cents:
            continue  # a different amount: maybe not all a gift, so you add it yourself
        session.add(
            Donation(
                date=payment.date,
                organization=charity.organization,
                amount_cents=-payment.amount_cents,
                kind=DonationKind.CASH,
                transaction_id=payment.id,
                auto_added=True,
            )
        )
        done.recorded += 1
    session.flush()
    return done
