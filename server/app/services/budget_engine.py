"""The suggested budget (roadmap #10): a 50/30/20 plan built from your own recent months.

The 50/30/20 guide splits take-home income into about 50% needs, 30% wants and 20% savings. It is
a rule of thumb, not a tax figure, so it lives here rather than in the tax data files.

How the plan is built, for income ``I`` (the planned monthly income, or else the average income of
the months looked at):
- **Averages** come from the 3 full months before the month planned for, using the monthly summary
  (so refunds, transfers and transfers into savings follow its rules). Months with no activity at
  all don't count towards the average.
- **Needs** keep their average: rent and bills can't be cut by a budget.
- **Savings** aim for 20% of ``I``, or what you already save if that's more.
- **Wants** get what's left, up to 30% of ``I``. Anything left after that goes to savings, so the
  plan uses the whole income. When needs and the savings goal already take more than ``I``, wants
  get nothing and savings get whatever is left above needs.
- Inside wants and savings, the group's amount is shared by each category's average (an even split
  when the group has no history), in whole cents that add up exactly (largest remainder). Savings
  also share with money moved into savings accounts (10b), which belongs to no category: its part is
  ``savings_by_transfer_cents``, and with no savings categories it gets the whole savings amount.
- Averages are whole cents, rounded down (towards minus infinity for a negative average).
- Applying as percentages needs an income to take shares of: without a planned income, the average
  income is saved as the planned income, so the percentages mean the same amounts as suggested.

These are suggestions to start from; nothing changes until the person applies them.
"""

from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Category, CategoryGroup
from app.percent import percent_bp, share_of
from app.schemas.budget_engine import (
    ApplyResult,
    BudgetSuggestion,
    SuggestedCategory,
    SuggestedGroup,
)
from app.schemas.budget_plan import BudgetPlanIn
from app.schemas.summary import MonthlySummary
from app.services.budget_plan import get_plan, save_plan
from app.services.summary import monthly_summary
from app.services.trend import months_ending

LOOKBACK_MONTHS = 3
GUIDE_BP = {CategoryGroup.NEEDS: 5_000, CategoryGroup.WANTS: 3_000, CategoryGroup.SAVINGS: 2_000}
_PLANNED = tuple(GUIDE_BP)
NO_INCOME = (
    "There's no income to plan with yet. Give your paychecks an income category, or set a planned "
    "monthly income on the Categories page."
)


def months_before(year: int, month: int, count: int) -> list[tuple[int, int]]:
    """The ``count`` full months before ``year-month`` as (year, month), oldest first."""
    before = year * 12 + (month - 1) - 1
    return months_ending(before // 12, before % 12 + 1, count)


def _has_data(s: MonthlySummary) -> bool:
    return any(g.actual_cents for g in s.groups) or s.unassigned_count > 0


def split(total: int, weights: list[int]) -> list[int]:
    """Share ``total`` cents by ``weights`` in whole cents that add up to ``total`` exactly.

    Largest remainder: each gets its rounded-down share, then the leftover cents go to the biggest
    remainders (earlier first on ties). All-zero weights split evenly.
    """
    if not weights:
        return []
    if sum(weights) <= 0:
        weights = [1] * len(weights)
    whole = sum(weights)
    shares = [total * w // whole for w in weights]
    order = sorted(range(len(weights)), key=lambda i: (-(total * weights[i] % whole), i))
    for i in order[: total - sum(shares)]:
        shares[i] += 1
    return shares


def group_amounts(income: int, needs: int, saved: int) -> dict[CategoryGroup, int]:
    """How much of ``income`` each group gets (see the module docstring)."""
    if income <= 0:
        return dict.fromkeys(_PLANNED, 0)
    savings_goal = max(share_of(income, GUIDE_BP[CategoryGroup.SAVINGS]), saved)
    room = income - needs - savings_goal
    if room < 0:
        wants = 0
    else:
        wants = min(room, share_of(income, GUIDE_BP[CategoryGroup.WANTS]))
    return {
        CategoryGroup.NEEDS: needs,
        CategoryGroup.WANTS: wants,
        CategoryGroup.SAVINGS: max(0, income - needs - wants),
    }


def split_savings(amount: int, weights: list[int], transfer_weight: int) -> tuple[list[int], int]:
    """Share the savings amount between savings categories and moves into savings accounts."""
    if not weights:
        return [], amount
    if sum(weights) + transfer_weight <= 0:
        return split(amount, weights), 0
    *shares, by_transfer = split(amount, [*weights, transfer_weight])
    return shares, by_transfer


def _notes(months_with_data: int, income: int, needs: int, saved: int) -> list[str]:
    if months_with_data == 0:
        return ["There's no history yet. Add or import a few months of transactions first."]
    notes = []
    if months_with_data < LOOKBACK_MONTHS:
        notes.append(
            f"This is based on only {months_with_data} month(s) of history, so treat it as a "
            "rough start."
        )
    if income <= 0:
        return [*notes, NO_INCOME]
    savings_goal = share_of(income, GUIDE_BP[CategoryGroup.SAVINGS])
    if needs > share_of(income, GUIDE_BP[CategoryGroup.NEEDS]):
        notes.append(
            "Your needs take more than half of your income. The plan keeps them as they are and "
            "leaves less for wants."
        )
    if needs >= income:
        notes.append(
            "Your needs alone are as much as your income or more, so the plan has nothing left "
            "for wants or savings."
        )
    elif needs + savings_goal > income:
        notes.append("Your needs leave less than 20% of your income for savings.")
    if saved > savings_goal:
        notes.append("You already save more than 20% of your income. The plan keeps that up.")
    return notes


def _averages(used: list[MonthlySummary]):
    """Per category, per group, income and moves into savings: averages over months with data."""
    count = len(used)

    def average(values) -> int:
        return sum(values) // count if count else 0

    ids = {t.category_id for s in used for t in s.categories}
    by_category = {
        i: average(t.actual_cents for s in used for t in s.categories if t.category_id == i)
        for i in ids
    }
    by_group = {
        g: average(x.actual_cents for s in used for x in s.groups if x.group == g) for g in _PLANNED
    }
    income = max(0, average(s.income_cents for s in used))
    return by_category, by_group, income, average(s.saved_by_transfer_cents for s in used)


def suggest(session: Session, year: int, month: int) -> BudgetSuggestion:
    months = months_before(year, month, LOOKBACK_MONTHS)
    used = [s for s in (monthly_summary(session, y, m) for y, m in months) if _has_data(s)]
    by_category, by_group, average_income, by_transfer = _averages(used)
    categories = [
        c for c in monthly_summary(session, year, month).categories if c.group in _PLANNED
    ]
    planned = get_plan(session).planned_income_cents
    income = planned if planned is not None else average_income

    average = {c.category_id: by_category.get(c.category_id, 0) for c in categories}
    needs = sum(
        max(0, average[c.category_id]) for c in categories if c.group == CategoryGroup.NEEDS
    )
    saved = max(0, by_group[CategoryGroup.SAVINGS])
    amounts = group_amounts(income, needs, saved)

    suggested: dict[int, int] = {}
    savings_by_transfer = 0
    for group in _PLANNED:
        members = [c for c in categories if c.group == group]
        weights = [max(0, average[c.category_id]) for c in members]
        if income <= 0:
            shares = [0] * len(members)
        elif group == CategoryGroup.NEEDS:
            shares = weights
        elif group == CategoryGroup.SAVINGS:
            shares, savings_by_transfer = split_savings(
                amounts[group], weights, max(0, by_transfer)
            )
        else:
            shares = split(amounts[group], weights)
        suggested.update(zip((c.category_id for c in members), shares, strict=True))

    def group_total(group: CategoryGroup) -> int:
        extra = savings_by_transfer if group == CategoryGroup.SAVINGS else 0
        return extra + sum(suggested[c.category_id] for c in categories if c.group == group)

    return BudgetSuggestion(
        month=f"{year:04d}-{month:02d}",
        looked_at=[f"{y:04d}-{m:02d}" for y, m in months],
        months_with_data=len(used),
        income_cents=income,
        income_source="planned" if planned is not None else "average",
        average_income_cents=average_income,
        savings_by_transfer_cents=savings_by_transfer,
        groups=[
            SuggestedGroup(
                group=g,
                guide_percent_bp=GUIDE_BP[g],
                average_cents=by_group[g],
                suggested_cents=group_total(g),
                suggested_percent_bp=percent_bp(group_total(g), income),
            )
            for g in _PLANNED
        ],
        categories=[
            SuggestedCategory(
                category_id=c.category_id,
                name=c.name,
                group=c.group,
                average_cents=average[c.category_id],
                current_budget_cents=c.budget_cents,
                suggested_cents=suggested[c.category_id],
                suggested_percent_bp=percent_bp(suggested[c.category_id], income),
            )
            for c in categories
        ],
        notes=_notes(len(used), income, needs, saved),
    )


def apply(session: Session, year: int, month: int, use: str) -> ApplyResult:
    """Save the suggestion as every needs, wants and savings category's budget.

    As percentages, a category whose suggestion rounds to 0.00% gets a $0 amount budget instead,
    since a percentage budget must be more than zero.
    """
    plan = suggest(session, year, month)
    if plan.income_cents <= 0:
        raise ApiError(409, "no_income", NO_INCOME)
    planned_now = None
    if use == "percentages" and plan.income_source == "average":
        planned_now = plan.income_cents
        save_plan(session, BudgetPlanIn(planned_income_cents=planned_now))
    for item in plan.categories:
        category = session.get(Category, item.category_id)
        if use == "percentages" and item.suggested_percent_bp:
            category.budget_percent_bp, category.budget_cents = item.suggested_percent_bp, 0
        else:
            category.budget_percent_bp, category.budget_cents = None, item.suggested_cents
    session.commit()
    return ApplyResult(updated=len(plan.categories), planned_income_cents=planned_now)
