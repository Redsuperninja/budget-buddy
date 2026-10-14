"""Check deposit sweeps by hand: the lines with "sweep" in them that aren't linked to a dividend or
trade yet, with the ones near each that could be its match, and a Link and Unlink of your own.

The finders (``sweeps``, ``combined_sweeps``) only link a sweep for exactly the opposite amount, in
the same account, from a day before to three days after. This shows what they left over, so a
broker's other habits (a sweep two weeks later, a few cents off) are easy to spot and fix:

- **Unlinked sweep lines**: every free sweep (``sweeps.candidates``) in any account.
- **Possible matches**: dividends and trades in the same account still without a sweep, from
  ``SUGGEST_DAYS`` before to ``SUGGEST_DAYS`` after, exact amounts first, then the closest dates.
- **Per account**: how many dividends and trades it has, how many have their sweep, and how many
  sweep lines are free. When those don't add up, something wasn't matched.

Linking by hand works like a found link: the sweep is left out of "needs a category" and of the
budget (``transaction_roles``), even one you gave a category. Since
the sweep's whole amount then stops counting, a link must be the same money (``fits``): the same
account (one in another account is real money moving between accounts), the opposite direction, at
most ``SUGGEST_DAYS`` apart, and amounts at most ``ALLOWED_GAP_CENTS`` or ``ALLOWED_GAP_PERCENT``
apart, whichever is more. Any gap at all must be confirmed (``confirm``): it won't be counted
anywhere. Only matches that fit are offered. A hand link is marked ``sweep_by_hand``, so "Match
everything again" leaves it alone. Unlink frees the sweep from every dividend and trade
it was linked to (``combined_sweeps.free_sweep``); the page offers it right after a Link, as Undo.
A link the finders made would come back the next time they look, so for a wrong one of those mark
the dividend or trade as not one instead.
"""

from typing import Literal

from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Account, BankTrade, Dividend, Transaction
from app.schemas.investing.sweep_check import (
    AccountCount,
    PossibleMatch,
    SweepCheck,
    UnlinkedSweep,
)
from app.services.investing.combined_sweeps import free_sweep
from app.services.investing.sweeps import candidates

SUGGEST_DAYS = 14
ALLOWED_GAP_CENTS = 100  # $1
ALLOWED_GAP_PERCENT = 1
Kind = Literal["dividend", "trade"]
MODELS = {"dividend": Dividend, "trade": BankTrade}


def _free_lines(session: Session, account_ids: set[int]) -> list[Transaction]:
    """Free sweep lines, but never a dividend's own payment (its description may say "sweep")."""
    paid = set(session.scalars(select(Dividend.transaction_id)))
    return [t for t in candidates(session, account_ids) if t.id not in paid]


def _waiting(session: Session) -> list[tuple[Kind, object, Transaction]]:
    """Every dividend and trade (not dismissed) still without a sweep, with its payment."""
    found = []
    for kind, model in MODELS.items():
        rows = session.execute(
            select(model, Transaction)
            .join(Transaction, Transaction.id == model.transaction_id)
            .where(model.dismissed.is_(False), model.sweep_transaction_id.is_(None))
        ).all()
        found += [(kind, record, paid) for record, paid in rows]
    return found


def gap(sweep: Transaction, paid: Transaction) -> int:
    """Cents by which the sweep doesn't undo the payment (0: exactly the same money)."""
    return abs(sweep.amount_cents + paid.amount_cents)


def fits(sweep: Transaction, paid: Transaction) -> str | None:
    """Why this sweep can't be the same money as this payment, or None if it can."""
    if paid.account_id != sweep.account_id:
        return "other_account"
    if (sweep.amount_cents > 0) == (paid.amount_cents > 0):
        return "same_direction"
    if abs((sweep.date - paid.date).days) > SUGGEST_DAYS:
        return "too_far"
    allowed = max(ALLOWED_GAP_CENTS, abs(paid.amount_cents) * ALLOWED_GAP_PERCENT // 100)
    return "too_different" if gap(sweep, paid) > allowed else None


REFUSED = {
    "other_account": "A sweep can only be linked to a dividend or trade in the same account.",
    "same_direction": "A sweep moves the cash the other way: this one goes in the same direction.",
    "too_far": f"A sweep can only be linked to one up to {SUGGEST_DAYS} days away.",
    "too_different": "The amounts are too far apart to be the same money.",
}


def _matches(sweep: Transaction, waiting: list) -> list[PossibleMatch]:
    near = [(kind, record, paid) for kind, record, paid in waiting if fits(sweep, paid) is None]
    near.sort(
        key=lambda m: (
            gap(sweep, m[2]),
            abs((m[2].date - sweep.date).days),
            m[2].id,
        )
    )
    return [
        PossibleMatch(
            kind=kind,
            record_id=record.id,
            transaction_id=paid.id,
            date=paid.date,
            description=paid.description,
            amount_cents=paid.amount_cents,
            exact=gap(sweep, paid) == 0,
            gap_cents=gap(sweep, paid),
            days_apart=(sweep.date - paid.date).days,
        )
        for kind, record, paid in near
    ]


def _counts(session: Session, free: list[Transaction]) -> list[AccountCount]:
    totals: dict[int, list[int]] = {}  # account id -> [dividends and trades, with a sweep]
    for model in MODELS.values():
        rows = session.execute(
            select(
                Transaction.account_id,
                func.count(),
                func.count(model.sweep_transaction_id),
            )
            .join(Transaction, Transaction.id == model.transaction_id)
            .where(model.dismissed.is_(False))
            .group_by(Transaction.account_id)
        ).all()
        for account_id, count, linked in rows:
            pair = totals.setdefault(account_id, [0, 0])
            pair[0] += count
            pair[1] += linked
    loose: dict[int, int] = {}
    for sweep in free:
        loose[sweep.account_id] = loose.get(sweep.account_id, 0) + 1
    ids = set(totals) | set(loose)
    names = dict(session.execute(select(Account.id, Account.name).where(Account.id.in_(ids))).all())
    return [
        AccountCount(
            account_id=i,
            account_name=names[i],
            payments=totals.get(i, [0, 0])[0],
            with_sweep=totals.get(i, [0, 0])[1],
            free_sweeps=loose.get(i, 0),
        )
        for i in sorted(ids, key=lambda i: names[i].lower())
    ]


def check(session: Session) -> SweepCheck:
    all_accounts = set(session.scalars(select(Account.id)))
    free = sorted(_free_lines(session, all_accounts), key=lambda t: (t.date, t.id), reverse=True)
    waiting = _waiting(session)
    names = dict(session.execute(select(Account.id, Account.name)).all())
    return SweepCheck(
        accounts=_counts(session, free),
        unlinked=[
            UnlinkedSweep(
                transaction_id=s.id,
                date=s.date,
                description=s.description,
                amount_cents=s.amount_cents,
                account_id=s.account_id,
                account_name=names[s.account_id],
                matches=_matches(s, waiting),
            )
            for s in free
        ],
        suggest_days=SUGGEST_DAYS,
    )


def link(session: Session, sweep_id: int, kind: Kind, record_id: int, confirm: bool) -> None:
    """Link this free sweep line to a dividend or trade that ``fits``. ``confirm``: you accept that
    a gap between the amounts won't be counted anywhere."""
    model = MODELS[kind]
    record = session.get(model, record_id)
    sweep = session.get(Transaction, sweep_id)
    if record is None or sweep is None:
        raise not_found("dividend or trade" if record is None else "sweep line")
    if record.dismissed:
        raise ApiError(409, "dismissed", f"That {kind} was marked as not one, so it has no sweep.")
    paid = session.get(Transaction, record.transaction_id)
    if refused := fits(sweep, paid):
        raise ApiError(409, refused, REFUSED[refused])
    if gap(sweep, paid) and not confirm:
        raise ApiError(
            409, "confirm_gap", "The amounts aren't the same. Confirm to link them anyway."
        )
    if sweep.id not in {t.id for t in _free_lines(session, {sweep.account_id})}:
        raise ApiError(
            409, "not_free", "That line is already linked, or isn't a sweep line that can be."
        )
    claimed = session.execute(
        update(model)
        .where(
            model.id == record.id,
            model.dismissed.is_(False),
            model.sweep_transaction_id.is_(None),
            # Still free when written: two Links at once can't share one sweep line.
            ~exists().where(Dividend.sweep_transaction_id == sweep.id),
            ~exists().where(BankTrade.sweep_transaction_id == sweep.id),
        )
        .values(sweep_transaction_id=sweep.id, sweep_by_hand=True)
    ).rowcount
    if not claimed:
        session.rollback()
        raise ApiError(
            409, "has_sweep", f"That {kind} or that line was just linked. Reload the page."
        )
    session.commit()


def unlink(session: Session, sweep_id: int) -> None:
    """Free this sweep from every dividend and trade it was linked to."""
    linked = any(
        session.scalar(select(func.count()).where(model.sweep_transaction_id == sweep_id))
        for model in MODELS.values()
    )
    if not linked:
        raise not_found("linked sweep")
    free_sweep(session, sweep_id)
    session.commit()
