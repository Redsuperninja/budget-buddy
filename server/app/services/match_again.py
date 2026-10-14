"""Match everything again: run every finder over all your transactions, so data imported before a
matching rule improved gets the same treatment as new data. Dividends, then stock trades (found
from a bank file or recorded by you), then deposit sweeps (one each, then one for several), then
transfers.

Sweep links are always made by Budget Buddy, so they're picked again with today's rules. It only
ever adds: a link the new pick left free is put back as it was, so nothing that was sorted before
comes back unsorted. Anything you decided stays: "not a dividend" and "not a trade", transfers you
linked or unlinked, categories, and recorded shares. Nothing here logs descriptions or amounts.
"""

import threading

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import BankTrade, Dividend
from app.schemas.transactions import MatchedAgain
from app.services.bank_trades import find_trades
from app.services.dividend_matching import find_dividends
from app.services.transfer_matching import match_transfers

MODELS = (Dividend, BankTrade)
_RUNNING = threading.Lock()
BUSY = "Budget Buddy is already matching everything again. Try again in a moment."


def _links(session: Session) -> dict[tuple[str, int], int]:
    """(table, record id) -> its sweep, for every linked dividend and trade."""
    return {
        (model.__tablename__, record_id): sweep_id
        for model in MODELS
        for record_id, sweep_id in session.execute(
            select(model.id, model.sweep_transaction_id).where(
                model.sweep_transaction_id.is_not(None)
            )
        )
    }


def _put_back(session: Session, before: dict, after: dict) -> None:
    """Links the new pick left free go back as they were (a group as a whole)."""
    free = set(before.values()) - set(after.values())
    for model in MODELS:
        ids = [
            record_id
            for (table, record_id), sweep_id in before.items()
            if table == model.__tablename__ and sweep_id in free and (table, record_id) not in after
        ]
        for record_id in ids:
            session.execute(
                update(model)
                .where(model.id == record_id, model.sweep_transaction_id.is_(None))
                .values(sweep_transaction_id=before[(model.__tablename__, record_id)])
            )


def match_again(session: Session) -> MatchedAgain:
    """One run at a time: it goes through all of history while holding the database."""
    if not _RUNNING.acquire(blocking=False):
        raise ApiError(409, "busy", BUSY)
    try:
        return _run(session)
    finally:
        _RUNNING.release()


def _run(session: Session) -> MatchedAgain:
    with session.begin_nested():  # all of it, or none
        before = _links(session)
        for model in MODELS:
            session.execute(update(model).values(sweep_transaction_id=None))
        dividends = find_dividends(session)
        trades = find_trades(session)  # sweeps for several at once, too
        _put_back(session, before, _links(session))
        transfers = match_transfers(session)
        after = _links(session)
    session.commit()
    changed = {sweep for key, sweep in after.items() if before.get(key) != sweep}
    return MatchedAgain(
        dividends_found=dividends.dividends,
        trades_found=trades.trades,
        sweeps_linked=len(changed),
        transfers_linked=transfers,
    )
