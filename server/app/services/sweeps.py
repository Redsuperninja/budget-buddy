"""Deposit sweeps: the line next to a dividend or a stock trade that moves the same cash between
the account and its sweep (like "CHASE DEPOSIT SWEEP JPMORGAN CHASE BANK NA INTRA-DAY DEPOSIT").
Shared by ``dividend_matching`` and ``bank_trades``, so both pick sweeps the same way and never the
same one.

A sweep is a regular transaction in the same account for exactly the opposite amount, from
``SWEEP_DAYS_BEFORE`` days before to ``SWEEP_DAYS_AFTER`` days after, with "sweep" in the
description, that isn't already a dividend's or a trade's sweep, or a trade itself. The closest
date wins, then the one added first.
"""

import datetime as dt
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction, TransactionKind
from app.services.transaction_roles import (
    bank_trade_sweeps,
    bank_trades,
    dividend_sweeps,
    donations,
    none_of,
    paycheck_deposits,
    stock_trades,
)

SWEEP_DAYS_BEFORE = 1
SWEEP_DAYS_AFTER = 3
SWEEP_WORDS = re.compile(r"(?<![a-z])sweep(?![a-z])", re.I)


def regular(query):
    """Regular transactions not already a transfer, a paycheck's deposit or a donation."""
    return query.where(
        Transaction.kind == TransactionKind.NORMAL,
        Transaction.transfer_pair_id.is_(None),
        *none_of(paycheck_deposits(), donations()),
    )


def _not_taken():
    """Conditions: not a linked sweep already, and not a trade itself (a trade is never a sweep)."""
    return none_of(
        dividend_sweeps(),
        bank_trade_sweeps(),
        bank_trades(include_dismissed=True),
        stock_trades(),
    )


def link_sweeps(session: Session, waiting: list) -> int:
    """``waiting``: (record, paid transaction) pairs, oldest first, whose record's
    ``sweep_transaction_id`` is still empty. Links each one's sweep if found; returns the count."""
    if not waiting:
        return 0
    sweeps = [
        t
        for t in session.scalars(
            regular(select(Transaction)).where(
                Transaction.account_id.in_({paid.account_id for _, paid in waiting}),
                *_not_taken(),
            )
        )
        if SWEEP_WORDS.search(t.description)
    ]
    linked = 0
    taken: set[int] = set()
    for record, paid in waiting:
        start = paid.date - dt.timedelta(days=SWEEP_DAYS_BEFORE)
        end = paid.date + dt.timedelta(days=SWEEP_DAYS_AFTER)
        fits = [
            s
            for s in sweeps
            if s.id not in taken
            and s.account_id == paid.account_id
            and s.amount_cents == -paid.amount_cents
            and start <= s.date <= end
        ]
        if fits:
            best = min(fits, key=lambda s: (abs((s.date - paid.date).days), s.id))
            record.sweep_transaction_id = best.id
            taken.add(best.id)
            linked += 1
    return linked
