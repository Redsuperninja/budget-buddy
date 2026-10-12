"""Auto-sort learning: after you pick the same category by hand for the same shop a few times,
Budget Buddy makes an auto-sort rule for it (``CategoryRule.learned``) and sorts the matching
transactions that have no category yet.

- "The same shop" is ``shop_key``: the start of the description, up to three words, skipping
  generic bank words ("POS", "DEBIT") and stopping at the first word with a digit (store numbers,
  dates). "STARBUCKS STORE 12345 SEATTLE" -> "STARBUCKS STORE". It's always a piece of the
  description, so as a rule's text it matches the same descriptions.
- A rule is learned once ``LEARN_AFTER`` hand-picked transactions with that key share a category
  and none with that key were picked into a different one.
- It never replaces or outranks a rule you made: if an existing rule at least as long already
  matches the description, nothing is learned. Nothing here logs descriptions.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CategoryRule, CategorySource, Transaction, TransactionKind
from app.services.budget.category_rules import apply_to_uncategorized

LEARN_AFTER = 3
MIN_LETTERS = 3
MAX_WORDS = 3
# Words banks put in front of the shop's name; skipped at the start of a description.
GENERIC_WORDS = frozenset(
    {
        "ACH", "CARD", "CHECKCARD", "CREDIT", "DEBIT", "ONLINE", "PAYMENT", "PMT", "POS",
        "PURCHASE", "RECURRING", "SQ", "TST", "VISA", "WITHDRAWAL", "PAYPAL",
    }
)  # fmt: skip


def shop_key(description: str) -> str | None:
    """The start of the description that names the shop, or None if there isn't a usable one."""
    words = description.split()
    start = 0
    while start < len(words) and words[start].strip("*#:-").upper() in GENERIC_WORDS:
        start += 1
    kept: list[str] = []
    for word in words[start:]:
        if any(ch.isdigit() for ch in word) or len(kept) == MAX_WORDS:
            break
        kept.append(word)
    if not kept:
        return None
    begin = description.index(kept[0], sum(len(w) for w in words[:start]))
    end = begin
    for word in kept:
        end = description.index(word, end) + len(word)
    key = description[begin:end]
    if sum(ch.isalpha() for ch in key) < MIN_LETTERS or len(key) > 100:
        return None
    return key


def _picks_by_category(session: Session, key: str) -> dict[int, int]:
    """Hand-picked categories of regular transactions whose description starts with ``key``."""
    rows = session.execute(
        select(Transaction.category_id, func.count())
        .where(
            Transaction.category_source == CategorySource.YOU.value,
            Transaction.kind == TransactionKind.NORMAL,
            Transaction.category_id.is_not(None),
            func.lower(func.substr(Transaction.description, 1, len(key))) == key.lower(),
        )
        .group_by(Transaction.category_id)
    )
    return dict(rows.all())


def _outranked(session: Session, key: str, description: str) -> bool:
    """True if a rule with this text exists, or an existing rule at least as long matches."""
    text = description.casefold()
    for pattern in session.scalars(select(CategoryRule.pattern)):
        folded = pattern.casefold()
        if folded == key.casefold() or (folded in text and len(folded) >= len(key)):
            return True
    return False


def learn_from_pick(session: Session, transaction: Transaction) -> str | None:
    """Call after a category was picked by hand (and flushed). Returns the learned rule's text,
    if this pick taught Budget Buddy a new rule; the caller commits."""
    if transaction.kind != TransactionKind.NORMAL or transaction.category_id is None:
        return None
    key = shop_key(transaction.description)
    if key is None or _outranked(session, key, transaction.description):
        return None
    picks = _picks_by_category(session, key)
    if picks.get(transaction.category_id, 0) < LEARN_AFTER or len(picks) > 1:
        return None
    session.add(CategoryRule(pattern=key, category_id=transaction.category_id, learned=True))
    session.flush()
    apply_to_uncategorized(session)  # commits
    return key


def picked_by_hand(session: Session, transaction: Transaction) -> str | None:
    """Note that the category was set by hand (not by a rule), then learn from it. Returns the
    learned rule's text, if any. The caller commits."""
    transaction.sorted_by_rule_id = None
    transaction.category_source = (
        CategorySource.YOU.value if transaction.category_id is not None else None
    )
    session.flush()
    return learn_from_pick(session, transaction)
