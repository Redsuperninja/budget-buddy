"""Auto-categorization rules (roadmap #9): "description contains this text" -> a category.

- Matching ignores upper and lower case (``casefold``) and looks anywhere in the description.
- When several rules match, the longest text wins, because it's the most specific ("AMAZON PRIME"
  beats "AMAZON"). Two rules of the same length: the older one wins.
- Rules only fill in a missing category on regular ("normal") transactions. They never change a
  category someone picked, and never touch transfers, refunds or adjustments, whose category
  follows other rules (docs/dev/architecture/ledger.md).
- They run when a bank file is imported, when a transaction is added without a category, and when
  asked to sort everything that has no category yet. Nothing here logs descriptions.
"""

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Category, CategoryRule, Transaction, TransactionKind
from app.schemas.category_rules import ApplyResult, RuleCreate, RuleUpdate

Matcher = Callable[[str], int | None]


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
    session.delete(get_rule(session, rule_id))
    session.commit()


def load_matcher(session: Session) -> Matcher:
    """A function from a description to the winning rule's category ID (or None)."""
    rules = sorted(
        session.execute(select(CategoryRule.id, CategoryRule.pattern, CategoryRule.category_id)),
        key=lambda r: (-len(r.pattern), r.id),
    )
    folded = [(r.pattern.casefold(), r.category_id) for r in rules]

    def match(description: str) -> int | None:
        text = description.casefold()
        return next((category_id for pattern, category_id in folded if pattern in text), None)

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
        category_id = match(transaction.description)
        if category_id is not None:
            transaction.category_id = category_id
            count += 1
    session.commit()
    return ApplyResult(categorized=count)
