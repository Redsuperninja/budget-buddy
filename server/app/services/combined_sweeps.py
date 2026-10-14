"""One deposit sweep for several dividends or trades: a broker that sweeps a day's cash at once,
like two buys on the same day paid by one "DEPOSIT SWEEP ... INTRA-DAY WITHDRWAL" for their total.

After each dividend and trade has had its own sweep picked (``sweeps.link_sweeps``), a free sweep
is linked to a group of two or more of those still without one, dividends and trades together, in
the same account and its date window, whose amounts add up to exactly the opposite of the sweep's.
A group of all money in or all money out is tried first, then a mixed one (a broker netting the
day's cash). The smallest group wins, then the one with the oldest payments; a sweep with more than
``MAX_NEAR`` waiting payments near it is left alone (too many ways to add up). Every member then
has the same ``sweep_transaction_id``, so it's left out like any linked sweep
(``transaction_roles``), even when you had given it a category. Sweeps are taken oldest first, each
with the first group that fits, not the best overall: with exact cents, the word "sweep" and a few
days, that's enough.

"Not a dividend" or "not a trade" on one member frees the sweep from the whole group
(``free_sweep``): the rest no longer add up to it. So does deleting a member's transaction, one at
a time or by undoing its import (``free_sweeps_of``).
"""

import datetime as dt
from itertools import combinations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import BankTrade, Dividend, Transaction
from app.services.sweeps import SWEEP_DAYS_AFTER, SWEEP_DAYS_BEFORE, candidates, in_window

MAX_NEAR = 10


def _waiting(session: Session) -> list[tuple[object, Transaction]]:
    """(record, payment) for every dividend and trade still without a sweep, oldest first."""
    found = []
    for model in (Dividend, BankTrade):
        found += session.execute(
            select(model, Transaction)
            .join(Transaction, Transaction.id == model.transaction_id)
            .where(model.dismissed.is_(False), model.sweep_transaction_id.is_(None))
        ).all()
    return sorted(found, key=lambda pair: (pair[1].date, pair[1].id))


def _group(sweep: Transaction, near: list) -> tuple | None:
    if len(near) > MAX_NEAR:
        return None
    same_sign = [(r, p) for r, p in near if (p.amount_cents > 0) == (sweep.amount_cents < 0)]
    for pool in (same_sign, near):
        for size in range(2, len(pool) + 1):
            for group in combinations(pool, size):  # oldest payments first, in order
                if sum(paid.amount_cents for _, paid in group) == -sweep.amount_cents:
                    return group
    return None


def _claim(session: Session, sweep: Transaction, group: tuple) -> bool:
    """Link the group to the sweep, unless another run got there first: each row only while it
    has no sweep, and the sweep only while nothing else has it. All or nothing (a savepoint)."""
    savepoint = session.begin_nested()
    claimed = 0
    for model in (Dividend, BankTrade):
        ids = [record.id for record, _ in group if isinstance(record, model)]
        if ids:
            claimed += session.execute(
                update(model)
                .where(model.id.in_(ids), model.sweep_transaction_id.is_(None))
                .values(sweep_transaction_id=sweep.id)
            ).rowcount
    sharing = sum(
        session.scalar(select(func.count()).where(model.sweep_transaction_id == sweep.id)) or 0
        for model in (Dividend, BankTrade)
    )
    if claimed == sharing == len(group):
        savepoint.commit()
        return True
    savepoint.rollback()
    return False


def link_combined(session: Session) -> int:
    """Link free sweeps that pay for several dividends or trades at once. Returns how many sweeps
    were linked. Not saved until the caller commits."""
    waiting = _waiting(session)
    if len(waiting) < 2:
        return 0
    first = min(paid.date for _, paid in waiting) - dt.timedelta(days=SWEEP_DAYS_BEFORE)
    last = max(paid.date for _, paid in waiting) + dt.timedelta(days=SWEEP_DAYS_AFTER)
    sweeps = [
        s
        for s in candidates(session, {p.account_id for _, p in waiting})
        if first <= s.date <= last
    ]
    linked, taken = 0, set()
    for sweep in sorted(sweeps, key=lambda s: (s.date, s.id)):
        near = [
            (record, paid)
            for record, paid in waiting
            if id(record) not in taken
            and paid.account_id == sweep.account_id
            and in_window(sweep, paid)
        ]
        group = _group(sweep, near)
        if group and _claim(session, sweep, group):
            taken.update(id(record) for record, _ in group)
            linked += 1
    return linked


def free_sweep(session: Session, sweep_id: int | None) -> None:
    """Unlink this sweep from every dividend and trade it was linked to."""
    if sweep_id is None:
        return
    for model in (Dividend, BankTrade):
        session.execute(
            update(model)
            .where(model.sweep_transaction_id == sweep_id)
            .values(sweep_transaction_id=None)
        )


def free_sweeps_of(session: Session, transaction_ids) -> None:
    """These transactions are about to be deleted: free the sweep of any dividend or trade paid
    by one of them, from its whole group. ``transaction_ids``: a select of ids, or a list."""
    for model in (Dividend, BankTrade):
        for sweep_id in session.scalars(
            select(model.sweep_transaction_id).where(
                model.transaction_id.in_(transaction_ids), model.sweep_transaction_id.is_not(None)
            )
        ).all():
            free_sweep(session, sweep_id)
