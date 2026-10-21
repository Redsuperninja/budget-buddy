"""Finding transfers between your own accounts automatically and linking them (``transfers``).

Two transactions are matched when all of these hold:

- one is money out and the other money in, for exactly the same amount, on different accounts;
- their dates are at most ``WINDOW_DAYS`` apart (a bank transfer or card payment can take a few
  days to show on the other side, longer over a weekend and holiday);
- both are regular transactions that aren't already linked, aren't a paycheck's deposit, a
  donation, a stock trade or a dividend's deposit sweep, weren't unlinked by you before
  (``auto_transfer_off``), and have no category yet or a transfer category (a category from you or
  a rule is respected);
- at least one description looks like a transfer (``TRANSFER_WORDS``), a credit card's side looks
  like a payment, and neither looks like a dividend, interest, an employer match, pay or a refund
  (``NOT_TRANSFER_WORDS``): an equal amount alone is too often a coincidence;
- the money leaves a checking, savings, investment, retirement, HSA, cash or other account (not a
  credit card or loan: those don't send money to your other accounts);
- each is the other's only best match: the closest date wins, and a tie is left for you to link.

Card payments not linked (yet) are then filed under "Payments" (``card_payments``). It runs after
a bank file is imported, after a transaction is added by hand, and when asked to
look through everything. Nothing here logs descriptions or amounts.
"""

import datetime as dt
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, defer, lazyload

from app.models import (
    Account,
    AccountKind,
    Category,
    CategoryGroup,
    Transaction,
)
from app.services.ledger.card_payments import file_card_payments
from app.services.ledger.transaction_roles import free_to_move
from app.services.ledger.transfer_words import (
    CARD_PAYMENT_WORDS,
    NOT_TRANSFER_WORDS,
    TRANSFER_WORDS,
)
from app.services.ledger.transfers import pair_up
from app.transfer_types import CANT_SEND

WINDOW_DAYS = 5


def _eligible(session: Session) -> list[tuple[Transaction, AccountKind]]:
    transfer_categories = select(Category.id).where(Category.group == CategoryGroup.TRANSFER)
    rows = session.execute(
        select(Transaction, Account.kind)
        .options(  # thousands of rows: skip the encrypted notes and the linked rows nobody reads
            defer(Transaction.notes),
            lazyload(Transaction.account),
            lazyload(Transaction.transfer_partner),
            lazyload(Transaction.donation),
        )
        .join(Account, Account.id == Transaction.account_id)
        .where(
            *free_to_move(),
            Transaction.amount_cents != 0,
            Transaction.category_id.is_(None) | Transaction.category_id.in_(transfer_categories),
        )
    )  # fmt: skip
    return [(t, kind) for t, kind in rows.all() if not NOT_TRANSFER_WORDS.search(t.description)]


def _looks_like_transfer(out: Transaction, into: Transaction, into_kind: AccountKind) -> bool:
    if into_kind == AccountKind.CREDIT_CARD and not CARD_PAYMENT_WORDS.search(into.description):
        return False  # a refund or credit on the card, not a payment
    return bool(TRANSFER_WORDS.search(out.description) or TRANSFER_WORDS.search(into.description))


def _best(candidates: list[tuple[int, Transaction]]) -> Transaction | None:
    """The single closest candidate (by days apart), or None if there's none or a tie."""
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    return candidates[0][1]


def match_transfers(session: Session, only_ids: set[int] | None = None) -> int:
    """Link every clear transfer pair (at least one side in ``only_ids``, if given). Returns how
    many pairs were linked; the caller commits."""
    rows = _eligible(session)
    outs = [t for t, kind in rows if t.amount_cents < 0 and kind not in CANT_SEND]
    kinds = {t.id: kind for t, kind in rows}
    ins_by_amount: dict[int, list[Transaction]] = defaultdict(list)
    for t, _kind in rows:
        if t.amount_cents > 0:
            ins_by_amount[t.amount_cents].append(t)
    window = dt.timedelta(days=WINDOW_DAYS)

    def partners_of_out(out: Transaction) -> list[tuple[int, Transaction]]:
        return [
            (abs((t.date - out.date).days), t)
            for t in ins_by_amount.get(-out.amount_cents, [])
            if t.account_id != out.account_id
            and abs(t.date - out.date) <= window
            and _looks_like_transfer(out, t, kinds[t.id])
        ]

    outs_by_amount: dict[int, list[Transaction]] = defaultdict(list)
    for out in outs:
        outs_by_amount[-out.amount_cents].append(out)

    def partners_of_in(into: Transaction) -> list[tuple[int, Transaction]]:
        return [
            (abs((o.date - into.date).days), o)
            for o in outs_by_amount.get(into.amount_cents, [])
            if o.account_id != into.account_id
            and abs(o.date - into.date) <= window
            and _looks_like_transfer(o, into, kinds[into.id])
        ]

    linked, known = 0, {}
    for out in sorted(outs, key=lambda t: (t.date, t.id)):
        into = _best(partners_of_out(out))
        if into is None or _best(partners_of_in(into)) is not out:
            continue
        if only_ids is not None and out.id not in only_ids and into.id not in only_ids:
            continue
        pair_up(session, out, into, known)
        linked += 1
    file_card_payments(session, only_ids)  # card payments without their other side, too
    return linked
