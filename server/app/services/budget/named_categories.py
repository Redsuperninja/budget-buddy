"""Categories Budget Buddy files things under by name ("Charitable giving", "Gifts", "Dividends"),
made the first time they're needed.

They're found by name, ignoring upper and lower case, so renaming one means Budget Buddy makes a
fresh one next time. Names are unique, so a same-named category in a group that doesn't fit (an
income category called "Gifts", say) is never used and blocks making one: the caller decides what
to do then.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, CategoryGroup


def find_or_make(
    session: Session, name: str, fits: set[CategoryGroup], new_group: CategoryGroup
) -> int | None:
    """The id of the category called ``name`` in one of the ``fits`` groups, made in
    ``new_group`` if there isn't one (not saved until the caller commits). None if the name is
    taken by a category in another group."""
    wanted = name.casefold()
    matches = [c for c in session.scalars(select(Category)) if c.name.casefold() == wanted]
    fitting = [c for c in matches if c.group in fits]
    if fitting:
        return fitting[0].id
    if matches:
        return None
    category = Category(name=name, group=new_group, budget_cents=0)
    session.add(category)
    session.flush()
    return category.id
