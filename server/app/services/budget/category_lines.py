"""One row per category line: the shared reader for totals by category (ADR-0017).

An unsplit transaction is one line (its own category, which may be NULL); a split transaction is
one line per part and never itself, since its own ``category_id`` is NULL and ignored. Each line
carries the transaction's id, date, kind and account, and the line's category and amount (integer
cents), so a grouped total over the lines never counts a split transaction twice.

Every reader of categories (monthly summary, spending pace, the category filter) uses this
instead of ``Transaction.category_id``.
"""

from sqlalchemy import Subquery, exists, select, union_all

from app.models import Transaction, TransactionSplit


def category_lines(*conditions) -> Subquery:
    """The lines as a subquery with columns ``transaction_id``, ``date``, ``kind``, ``account_id``,
    ``category_id`` and ``amount_cents``. ``conditions`` are filters on ``Transaction`` (date,
    kind, roles) applied to both halves, so a split transaction is kept or dropped as a whole."""
    unsplit = select(
        Transaction.id.label("transaction_id"),
        Transaction.date.label("date"),
        Transaction.kind.label("kind"),
        Transaction.account_id.label("account_id"),
        Transaction.category_id.label("category_id"),
        Transaction.amount_cents.label("amount_cents"),
    ).where(
        ~exists().where(TransactionSplit.transaction_id == Transaction.id),
        *conditions,
    )
    parts = (
        select(
            Transaction.id.label("transaction_id"),
            Transaction.date.label("date"),
            Transaction.kind.label("kind"),
            Transaction.account_id.label("account_id"),
            TransactionSplit.category_id.label("category_id"),
            TransactionSplit.amount_cents.label("amount_cents"),
        )
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(*conditions)
    )
    return union_all(unsplit, parts).subquery("category_lines")
