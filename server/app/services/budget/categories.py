"""Budget categories: list, add, rename, remove (when unused), and set the monthly budget (an amount or a percentage)."""

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Category, CategoryGroup, Receipt, Transaction
from app.schemas.budget.categories import INCOME_NO_BUDGET, CategoryCreate, CategoryUpdate


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
    if category.group == CategoryGroup.INCOME and (
        changes.get("budget_cents") or changes.get("budget_percent_bp") is not None
    ):
        raise ApiError(422, "validation_error", INCOME_NO_BUDGET)
    if "budget_cents" in changes:
        changes["budget_percent_bp"] = None  # back to an amount budget
    elif changes.get("budget_percent_bp") is not None:
        changes["budget_cents"] = 0
    for field, value in changes.items():
        setattr(category, field, value)
    _commit(session)
    return category


def delete_category(session: Session, category_id: int) -> None:
    """Delete a category nothing uses. One with transactions or receipts is kept: deleting it would
    leave them uncategorized. So is one a linked transfer goes back to when unlinked
    (pre_transfer_category_id has no foreign key). Its auto-sort rules go with it (cascade)."""
    category = get_category(session, category_id)
    used = session.scalar(
        select(
            exists().where(Transaction.category_id == category_id)
            | exists().where(Transaction.pre_transfer_category_id == category_id)
            | exists().where(Receipt.category_id == category_id)
        )
    )
    if used:
        raise ApiError(
            409,
            "category_in_use",
            "This category has transactions or receipts, so it can't be deleted. "
            "Move them to another category first.",
        )
    session.delete(category)
    session.commit()
