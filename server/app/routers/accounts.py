from fastapi import APIRouter, status

from app.deps import LOCAL_ONLY, SessionDep
from app.schemas.accounts import AccountCreate, AccountOut, AccountUpdate
from app.services import accounts as service

router = APIRouter(prefix="/api/local/accounts", tags=["accounts"], dependencies=LOCAL_ONLY)


@router.get("")
def list_accounts(session: SessionDep) -> list[AccountOut]:
    return service.list_accounts(session)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_account(data: AccountCreate, session: SessionDep) -> AccountOut:
    return service.create_account(session, data)


@router.get("/{account_id}")
def get_account(account_id: int, session: SessionDep) -> AccountOut:
    return service.account_out(session, account_id)


@router.patch("/{account_id}")
def update_account(account_id: int, data: AccountUpdate, session: SessionDep) -> AccountOut:
    return service.update_account(session, account_id, data)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, session: SessionDep) -> None:
    service.delete_account(session, account_id)
