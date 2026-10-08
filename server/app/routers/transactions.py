import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import Offset, PathId, QueryId, SessionDep
from app.models import CategorySource, TransactionKind
from app.schemas.transactions import (
    TransactionCreate,
    TransactionOut,
    TransactionPage,
    TransactionUpdate,
    TransferLink,
)
from app.services import gift_categories
from app.services import transactions as service

router = APIRouter(prefix="/api/local/transactions", tags=["transactions"])


@router.get("")
def list_transactions(
    session: SessionDep,
    account_id: QueryId = None,
    category_id: QueryId = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    kind: TransactionKind | None = None,
    q: Annotated[str | None, Query(max_length=200, description="Text in the description")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Offset = 0,
    sorted_by: Annotated[
        CategorySource | None, Query(description='"rule": auto-sorted; "you": picked by hand')
    ] = None,
) -> TransactionPage:
    filters = service.TransactionFilters(
        account_id, category_id, date_from, date_to, kind, q, limit, offset, sorted_by
    )
    return service.list_transactions(session, filters)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_transaction(data: TransactionCreate, session: SessionDep) -> TransactionOut:
    return service.create_transaction(session, data)


@router.get("/{transaction_id}")
def get_transaction(transaction_id: PathId, session: SessionDep) -> TransactionOut:
    return service.get_transaction(session, transaction_id)


@router.patch("/{transaction_id}")
def update_transaction(
    transaction_id: PathId, data: TransactionUpdate, session: SessionDep
) -> TransactionOut:
    return service.update_transaction(session, transaction_id, data)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: PathId, session: SessionDep) -> None:
    service.delete_transaction(session, transaction_id)


@router.post("/{transaction_id}/transfer")
def link_transfer(
    transaction_id: PathId, data: TransferLink, session: SessionDep
) -> TransactionOut:
    return service.link_transfer(session, transaction_id, data.other_id)


@router.delete("/{transaction_id}/transfer")
def unlink_transfer(transaction_id: PathId, session: SessionDep) -> TransactionOut:
    return service.unlink_transfer(session, transaction_id)


@router.post("/{transaction_id}/personal-gift")
def mark_personal_gift(transaction_id: PathId, session: SessionDep) -> TransactionOut:
    """File a payment under "Gifts" (a present for someone; not a tax record)."""
    return gift_categories.mark_personal_gift(session, transaction_id)
