from fastapi import APIRouter, status

from app.deps import PathId, SessionDep
from app.schemas.imports import ImportOut
from app.services import imports as service

router = APIRouter(prefix="/api/local/imports", tags=["imports"])


@router.get("")
def list_imports(session: SessionDep) -> list[ImportOut]:
    """Every file you imported, newest first."""
    return service.list_imports(session)


@router.delete("/{import_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_import(import_id: PathId, session: SessionDep) -> None:
    """Undo an import: delete everything it added."""
    service.remove(session, import_id)
