"""Budget categories: list, add, rename, and set the monthly budget (an amount or a percentage)."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Category, CategoryGroup
from app.schemas.categories import INCOME_PERCENT, CategoryCreate, CategoryUpdate


def _name_taken() -> ApiError:
    return ApiError(409, "name_taken", "You already have a category with that name.")


def _check_name_free(session: Session, name: str, own_id: int | None = None) -> None:
    # Compared in Python with casefold(), so "Strasse" and "STRASSE" count as the same name.
    wanted = name.casefold()
    for category_id, existing in session.execute(select(Category.id, Category.name)):
        if category_id != own_id and existing.casefold() == wanted:
            raise _name_taken()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:  # two requests added the same name at once
        session.rollback()
        raise _name_taken() from None


def get_category(session: Session, category_id: int) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise not_found("category")
    return category


def list_categories(session: Session) -> list[Category]:
    return list(session.scalars(select(Category).order_by(Category.group, Category.name)))


def create_category(session: Session, data: CategoryCreate) -> Category:
    _check_name_free(session, data.name)
    category = Category(**data.model_dump())
    session.add(category)
    _commit(session)
    return category


def update_category(session: Session, category_id: int, data: CategoryUpdate) -> Category:
    category = get_category(session, category_id)
    changes = data.changes()
    if "name" in changes:
        _check_name_free(session, changes["name"], own_id=category.id)
    if "budget_cents" in changes:
        changes["budget_percent_bp"] = None  # back to an amount budget
    elif changes.get("budget_percent_bp") is not None:
        if category.group == CategoryGroup.INCOME:
            raise ApiError(422, "validation_error", INCOME_PERCENT)
        changes["budget_cents"] = 0
    for field, value in changes.items():
        setattr(category, field, value)
    _commit(session)
    return category
