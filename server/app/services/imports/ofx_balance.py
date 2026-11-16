"""The statement balance a bank file offers for "Match your bank's balance" (roadmap 26-3).

Offer only: nothing is saved here. The one writer stays ``account_balance.set_balance``.
"""

from app.schemas.imports.ofx_import import OfxStatementBalance
from app.services.imports import ofx_parsing as parsing


def offered_balance(
    statement: parsing.OfxStatement, flip: bool, undecided: bool
) -> OfxStatementBalance | None:
    """The file's ledger balance and its date, or None when there is none or it isn't safe yet.

    ``set_balance`` takes the account's balance in the same signs as its transactions (a card's
    owed amount is negative). OFX already writes a card's owed amount as negative, so the number is
    offered as is. When the user flips a card file's signs, the file wrote everything backwards,
    the balance included, so it flips with them and matches the rows. While a backwards-looking
    card file still waits for that choice (``undecided``) nothing is offered.
    """
    if undecided or statement.balance_cents is None or statement.balance_date is None:
        return None
    cents = -statement.balance_cents if flip else statement.balance_cents
    return OfxStatementBalance(balance_cents=cents, date=statement.balance_date)
