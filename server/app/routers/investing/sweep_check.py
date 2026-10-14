"""Checking deposit sweeps by hand (services/investing/sweep_check.py), under /stocks so a joined
computer may use it like the rest of the Investments page."""

from fastapi import APIRouter, status

from app.deps import PathId, SessionDep
from app.schemas.investing.sweep_check import SweepCheck, SweepLink
from app.services.investing import sweep_check as service

router = APIRouter(prefix="/api/local/stocks/sweeps", tags=["stocks"])


@router.get("")
def check(session: SessionDep) -> SweepCheck:
    """Sweep lines not linked yet, with possible matches, and counts per account."""
    return service.check(session)


@router.post("/{sweep_id}/link", status_code=status.HTTP_204_NO_CONTENT)
def link(sweep_id: PathId, data: SweepLink, session: SessionDep) -> None:
    """Link a free sweep line to a dividend or trade in the same account."""
    service.link(session, sweep_id, data.kind, data.record_id, data.confirm)


@router.post("/{sweep_id}/unlink", status_code=status.HTTP_204_NO_CONTENT)
def unlink(sweep_id: PathId, session: SessionDep) -> None:
    """Free a sweep from every dividend and trade it was linked to."""
    service.unlink(session, sweep_id)
