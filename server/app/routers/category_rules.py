from fastapi import APIRouter, status

from app.deps import PathId, SessionDep
from app.schemas.category_rules import ApplyResult, RuleCreate, RuleOut, RuleUpdate
from app.services import category_rules as service

router = APIRouter(prefix="/api/local/category-rules", tags=["category rules"])


@router.get("")
def list_rules(session: SessionDep) -> list[RuleOut]:
    return service.list_rules(session)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rule(data: RuleCreate, session: SessionDep) -> RuleOut:
    return service.create_rule(session, data)


# Declared before "/{rule_id}" so "apply" isn't read as an ID.
@router.post("/apply")
def apply_rules(session: SessionDep) -> ApplyResult:
    """Sort every regular transaction that has no category yet."""
    return service.apply_to_uncategorized(session)


@router.get("/{rule_id}")
def get_rule(rule_id: PathId, session: SessionDep) -> RuleOut:
    return service.get_rule(session, rule_id)


@router.patch("/{rule_id}")
def update_rule(rule_id: PathId, data: RuleUpdate, session: SessionDep) -> RuleOut:
    return service.update_rule(session, rule_id, data)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: PathId, session: SessionDep) -> None:
    service.delete_rule(session, rule_id)
