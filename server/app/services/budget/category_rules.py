"""Auto-categorization rules (roadmap #9): "description contains this text" -> a category.

- Matching ignores upper and lower case (``casefold``) and looks anywhere in the description.
- When several rules match, the longest text wins, because it's the most specific ("AMAZON PRIME"
  beats "AMAZON"). Two rules of the same length: the older one wins.
- Rules only fill in a missing category on regular ("normal") transactions. They never change a
  category someone picked, and never touch transfers, refunds or adjustments, whose category
  follows other rules (docs/dev/architecture/ledger.md).
- They run when a bank file is imported, when a transaction is added without a category, and when
  asked to sort everything that has no category yet. Nothing here logs descriptions.
- A transaction sorted by a rule remembers it (``category_source`` "rule", ``sorted_by_rule_id``),
  so everything auto-sorted can be listed. Rules can also be learned (category_learning.py).
"""

from collections.abc import Callable
from typing import NamedTuple

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Category, CategoryRule, CategorySource, Transaction, TransactionKind
from app.schemas.budget.category_rules import ApplyResult, RuleCreate, RuleUpdate


class RuleMatch(NamedTuple):
    rule_id: int
    category_id: int


Matcher = Callable[[str], RuleMatch | None]


def rule_fields(match: RuleMatch | None) -> dict:
    """The transaction fields for a rule's result: its category, and that the rule sorted it."""
    if match is None:
        return {"category_id": None, "category_source": None, "sorted_by_rule_id": None}
    return {
        "category_id": match.category_id,
        "category_source": CategorySource.RULE.value,
        "sorted_by_rule_id": match.rule_id,
    }


def _pattern_taken() -> ApiError:
    return ApiError(409, "pattern_taken", "You already have a rule for that text.")


def _check_pattern_free(session: Session, pattern: str, own_id: int | None = None) -> None:
    wanted = pattern.casefold()
    for rule_id, existing in session.execute(select(CategoryRule.id, CategoryRule.pattern)):
        if rule_id != own_id and existing.casefold() == wanted:
            raise _pattern_taken()


def _check_category(session: Session, category_id: int | None) -> None:
    if category_id is not None and session.get(Category, category_id) is None:
        raise not_found("category")


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:  # two requests added the same text at once
        session.rollback()
        raise _pattern_taken() from None


def get_rule(session: Session, rule_id: int) -> CategoryRule:
    rule = session.get(CategoryRule, rule_id)
    if rule is None:
        raise not_found("rule")
    return rule


def list_rules(session: Session) -> list[CategoryRule]:
    return list(session.scalars(select(CategoryRule).order_by(CategoryRule.pattern)))


def sorted_counts(session: Session) -> dict[int, int]:
    """How many transactions each rule sorted (and that still have that rule's sorting)."""
    rows = session.execute(
        select(Transaction.sorted_by_rule_id, func.count())
        .where(Transaction.sorted_by_rule_id.is_not(None))
        .group_by(Transaction.sorted_by_rule_id)
    )
    return dict(rows.all())


def create_rule(session: Session, data: RuleCreate) -> CategoryRule:
    _check_pattern_free(session, data.pattern)
    _check_category(session, data.category_id)
    rule = CategoryRule(**data.model_dump())
    session.add(rule)
    _commit(session)
    return rule


def update_rule(session: Session, rule_id: int, data: RuleUpdate) -> CategoryRule:
    rule = get_rule(session, rule_id)
    changes = data.changes()
    if "pattern" in changes:
        _check_pattern_free(session, changes["pattern"], own_id=rule.id)
    _check_category(session, changes.get("category_id"))
    for field, value in changes.items():
        setattr(rule, field, value)
    _commit(session)
    return rule


def delete_rule(session: Session, rule_id: int) -> None:
    """Delete it. Transactions it sorted keep their category, but no longer name the rule."""
    session.delete(get_rule(session, rule_id))
    session.execute(
        update(Transaction)
        .where(Transaction.sorted_by_rule_id == rule_id)
        .values(sorted_by_rule_id=None)
    )
    session.commit()


def load_matcher(session: Session) -> Matcher:
    """A function from a description to the winning rule (its ID and category), or None."""
    rules = sorted(
        session.execute(select(CategoryRule.id, CategoryRule.pattern, CategoryRule.category_id)),
        key=lambda r: (-len(r.pattern), r.id),
    )
    folded = [(r.pattern.casefold(), RuleMatch(r.id, r.category_id)) for r in rules]

    def match(description: str) -> RuleMatch | None:
        text = description.casefold()
        return next((found for pattern, found in folded if pattern in text), None)

    return match


def apply_to_uncategorized(session: Session) -> ApplyResult:
    """Sort every regular transaction that has no category yet. Returns how many got one."""
    match = load_matcher(session)
    count = 0
    for transaction in session.scalars(
        select(Transaction).where(
            Transaction.category_id.is_(None), Transaction.kind == TransactionKind.NORMAL
        )
    ):
        found = match(transaction.description)
        if found is not None:
            for field, value in rule_fields(found).items():
                setattr(transaction, field, value)
            count += 1
    session.commit()
    return ApplyResult(categorized=count)
