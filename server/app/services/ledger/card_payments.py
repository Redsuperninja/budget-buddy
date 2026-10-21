"""Credit card payments go in the "Payments" category (transfer group) on both sides, the money
out of your bank account and the money into the card, so a card payment is clearly marked even
before, or without, its other side being linked. It never counts as spending: the card's charges
are the spending. Linked card payments get it when they're linked (``transfer_categories``).

Not linked (yet), a regular transaction with no category is filed under "Payments" when:

- it's money into a credit card that says it's a payment (``CARD_SIDE_WORDS``; never a merchant's
  credit or adjustment, ``NOT_CARD_SIDE_WORDS``), or
- it's money out of another account (not a card or loan) that looks like a payment
  (``CARD_PAYMENT_WORDS``), names a credit card (``CARD_WORDS``) and names one of the credit card
  accounts you added (a word of its name or bank, ``_names_your_card``). A payment to a card you
  haven't added is the only record of that card's spending, so it's left to count. Never a
  debit-card purchase, or a loan or savings account at a lender that also issues cards
  (``NOT_CARD_PAYMENT_WORDS``): that's real spending, a loan payment or saving.
- it's a card payment returned or reversed (``RETURNED_WORDS``): money back into the bank account,
  or out of the card. It cancels the payment, so it's filed with it rather than counted as income
  or spending. Never a fee (``FEE_WORDS``): that's a real charge.

Never one that otherwise looks like a refund, interest, a dividend, pay or a fee
(``NOT_TRANSFER_WORDS``, ``FEE_WORDS``), one you took out of a transfer or of "Payments"
(``auto_transfer_off``: you decide), or one that's already a paycheck's deposit, a donation, a
dividend, a trade or a sweep (``transaction_roles.free_to_move``). A category from you or a
rule is respected; ``category_source`` stays empty (Budget Buddy's choice, as for transfers). On a
full run (Find transfers, Match everything again) it also moves linked card payments still in
Budget Buddy's "Transfer" category to "Payments", for data from before this. Runs at the end of
transfer matching. Nothing here logs descriptions or
amounts.
"""

import re

from sqlalchemy import select, update
from sqlalchemy.orm import Session, defer, lazyload

from app.models import Account, AccountKind, Transaction
from app.services.ledger.transaction_roles import dividends, free_to_move, none_of
from app.services.ledger.transfer_categories import payments_category, transfer_category_id
from app.services.ledger.transfer_words import (
    CARD_PAYMENT_WORDS,
    CARD_SIDE_WORDS,
    CARD_WORDS,
    FEE_WORDS,
    GENERIC_WORDS,
    ISSUER_ALIASES,
    NOT_CARD_PAYMENT_WORDS,
    NOT_CARD_SIDE_WORDS,
    NOT_TRANSFER_WORDS,
    RETURNED_WORDS,
)
from app.transfer_types import CANT_SEND, TransferType


def _words(text: str) -> set[str]:
    found = {w for w in re.findall(r"[a-z]+", text.lower()) if w not in GENERIC_WORDS}
    for short, full in ISSUER_ALIASES.items():
        if short in found or full <= found:
            found |= {short, *full}
    return found


def your_card_words(session: Session) -> set[str]:
    """The words of your credit card accounts' names and banks ("Chase Freedom": chase, freedom)."""
    rows = session.execute(
        select(Account.name, Account.institution).where(Account.kind == AccountKind.CREDIT_CARD)
    )
    return set().union(*(_words(f"{name} {bank or ''}") for name, bank in rows))


def looks_like_card_payment(t: Transaction, kind: AccountKind, your_cards: set[str]) -> bool:
    """``your_cards``: ``your_card_words``."""
    words = t.description
    if FEE_WORDS.search(words):
        return False
    returned = bool(RETURNED_WORDS.search(words))
    if kind == AccountKind.CREDIT_CARD:  # a payment comes in; a returned one goes back out
        if not CARD_SIDE_WORDS.search(words) or NOT_CARD_SIDE_WORDS.search(words):
            return False
        if returned:
            return t.amount_cents < 0
        return t.amount_cents > 0 and not NOT_TRANSFER_WORDS.search(words)
    if kind in CANT_SEND or not CARD_PAYMENT_WORDS.search(words) or not CARD_WORDS.search(words):
        return False
    if NOT_CARD_PAYMENT_WORDS.search(words) or not _words(words) & your_cards:
        return False
    if returned:  # a payment goes out; a returned one comes back in
        return t.amount_cents > 0
    return t.amount_cents < 0 and not NOT_TRANSFER_WORDS.search(words)


def _unlinked(session: Session, ids: set[int] | None) -> list[Transaction]:
    query = (
        select(Transaction, Account.kind)
        .options(  # skip the encrypted notes and the linked rows nobody reads here
            defer(Transaction.notes),
            lazyload(Transaction.account),
            lazyload(Transaction.transfer_partner),
            lazyload(Transaction.donation),
        )
        .join(Account, Account.id == Transaction.account_id)
        .where(*free_to_move(), *none_of(dividends()), Transaction.category_id.is_(None))
    )
    if ids is not None:
        query = query.where(Transaction.id.in_(ids))
    your_cards = your_card_words(session)
    return [t for t, kind in session.execute(query) if looks_like_card_payment(t, kind, your_cards)]


def _linked_in_transfer(session: Session) -> list[int]:
    """Both sides of every linked card payment still in Budget Buddy's "Transfer" category."""
    transfer_id = transfer_category_id(session)
    if transfer_id is None:
        return []
    sides = session.scalars(
        select(Transaction).where(
            Transaction.transfer_pair_id.is_not(None),
            Transaction.category_id == transfer_id,
            Transaction.category_source.is_(None),
        )
    ).all()
    return [t.id for t in sides if t.transfer_type == TransferType.CARD_PAYMENT]


def file_card_payments(session: Session, ids: set[int] | None = None) -> int:
    """File card payments (among ``ids``, if given) under "Payments"; on a full run (no ``ids``),
    also older linked ones. Returns how many; the caller commits."""
    found = _unlinked(session, ids)
    linked = _linked_in_transfer(session) if ids is None else []
    if not found and not linked:
        return 0
    category_id = payments_category(session)
    if category_id is None:
        return 0
    for t in found:
        t.category_id = category_id
    if linked:
        session.execute(
            update(Transaction).where(Transaction.id.in_(linked)).values(category_id=category_id)
        )
    session.flush()
    return len(found) + len(linked)
