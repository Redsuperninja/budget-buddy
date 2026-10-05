from fastapi import APIRouter, status

from app.deps import PathId, SessionDep
from app.schemas.categories import CategoryCreate, CategoryOut, CategoryUpdate
from app.services import categories as service

router = APIRouter(prefix="/api/local/categories", tags=["categories"])


@router.get("")
def list_categories(session: SessionDep) -> list[CategoryOut]:
    return service.list_categories(session)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, session: SessionDep) -> CategoryOut:
    return service.create_category(session, data)


@router.get("/{category_id}")
def get_category(category_id: PathId, session: SessionDep) -> CategoryOut:
    return service.get_category(session, category_id)


@router.patch("/{category_id}")
def update_category(category_id: PathId, data: CategoryUpdate, session: SessionDep) -> CategoryOut:
    return service.update_category(session, category_id, data)
