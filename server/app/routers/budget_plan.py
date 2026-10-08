from fastapi import APIRouter

from app.deps import SessionDep
from app.schemas.budget_plan import BudgetPlanIn, BudgetPlanOut
from app.services import budget_plan as service

router = APIRouter(prefix="/api/local/budget/plan", tags=["budget"])


@router.get("")
def get_plan(session: SessionDep) -> BudgetPlanOut:
    return service.get_plan(session)


@router.put("")
def save_plan(data: BudgetPlanIn, session: SessionDep) -> BudgetPlanOut:
    return service.save_plan(session, data)
