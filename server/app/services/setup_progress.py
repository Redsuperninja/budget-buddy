"""First-start setup progress, kept by the Home Base (roadmap 25e, ADR-0015)."""

import datetime as dt
import logging

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.setup import SetupProgress
from app.schemas.setup import SetupProgressIn, SetupProgressOut

ROW_ID = 1
log = logging.getLogger(__name__)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)  # naive UTC, like the other timestamps


def _row(session: Session) -> SetupProgress:
    return session.get(SetupProgress, ROW_ID) or SetupProgress(id=ROW_ID)


def get_progress(session: Session) -> SetupProgressOut:
    row = session.get(SetupProgress, ROW_ID)
    return SetupProgressOut.model_validate(row) if row else SetupProgressOut()


def save_progress(session: Session, data: SetupProgressIn) -> SetupProgressOut:
    row = _row(session)
    for flag, column in (("finished", "finished_at"), ("phrase_saved", "phrase_saved_at")):
        wanted = getattr(data, flag)
        if wanted is None:
            continue
        if not wanted:
            setattr(row, column, None)
        elif getattr(row, column) is None:
            setattr(row, column, _now())
    session.add(row)
    session.commit()
    return SetupProgressOut.model_validate(row)


def record_backup(engine: Engine) -> None:
    """Note that a backup file was just written. Never stops a backup that worked: a database
    that isn't migrated yet (the command line on an old folder) simply has nothing to update."""
    try:
        with SessionLocal(bind=engine) as session:
            row = _row(session)
            row.last_backup_at = _now()
            session.add(row)
            session.commit()
    except SQLAlchemyError:
        log.warning("Couldn't note the time of the last backup; the backup itself is fine.")
