"""First-start setup progress (roadmap 25e, ADR-0015). This computer only, like Backups."""

from fastapi import APIRouter

from app.deps import SessionDep
from app.schemas.setup import SetupProgressIn, SetupProgressOut
from app.services import setup_progress as service

router = APIRouter(prefix="/api/local/setup", tags=["setup"])


@router.get("")
def get_setup(session: SessionDep) -> SetupProgressOut:
    return service.get_progress(session)


@router.put("")
def save_setup(data: SetupProgressIn, session: SessionDep) -> SetupProgressOut:
    return service.save_progress(session, data)
