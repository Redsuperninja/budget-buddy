import datetime as dt

from fastapi import APIRouter

from app.deps import SessionDep, parse_month
from app.schemas.budget_engine import ApplyChoice, ApplyResult, BudgetSuggestion
from app.schemas.budget_plan import BudgetPlanIn, BudgetPlanOut
from app.services import budget_engine
from app.services import budget_plan as service

router = APIRouter(prefix="/api/local/budget", tags=["budget"])


@router.get("/plan")
def get_plan(session: SessionDep) -> BudgetPlanOut:
    return service.get_plan(session)


@router.put("/plan")
def save_plan(data: BudgetPlanIn, session: SessionDep) -> BudgetPlanOut:
    return service.save_plan(session, data)


@router.get("/suggestion")
def suggestion(session: SessionDep, month: str = "") -> BudgetSuggestion:
    """A 50/30/20 plan from the 3 full months before ``month`` (this month if left out)."""
    year_month = parse_month(month) if month else (dt.date.today().year, dt.date.today().month)
    return budget_engine.suggest(session, *year_month)


@router.post("/suggestion/apply")
def apply_suggestion(data: ApplyChoice, session: SessionDep) -> ApplyResult:
    """Save the suggestion as the budget of every needs, wants and savings category."""
    return budget_engine.apply(session, *parse_month(data.month), data.use)
