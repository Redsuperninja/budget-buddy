"""Credit card files that list charges as positive numbers (and payments as negative), the other
way round from Budget Buddy (ledger.md, "Signs and balances": a charge is money out of the card).

Imported as they are, charges would add up to money you have instead of money you owe, and a card
payment would look like money out on both sides, so it never pairs with the checking side. So for a
credit card account, unless you chose yourself, the import checks the file and flips it when:

- it has payment lines ("PAYMENT THANK YOU", "AUTOPAY", ...) and most of them are money out, or
- it has none, and at least ``MOSTLY`` of at least ``MIN_ROWS`` amounts are money in (a card's lines
  are mostly charges).
"""

from app.services.ledger.transfer_words import CARD_PAYMENT_WORDS

MIN_ROWS = 3
MOSTLY = 0.8

FLIPPED = (
    "This card's file lists charges as positive numbers, so Budget Buddy flipped them: charges are "
    "money out and payments money in. If that's wrong, change it in the column choices."
)


def looks_flipped(rows: list[tuple[str, int]]) -> bool:
    """``rows``: (description, amount in cents) as read from the file."""
    amounts = [(d, c) for d, c in rows if c]
    payments = [c for d, c in amounts if CARD_PAYMENT_WORDS.search(d)]
    if payments:
        return sum(c < 0 for c in payments) * 2 > len(payments)
    if len(amounts) < MIN_ROWS:
        return False
    return sum(c > 0 for _, c in amounts) >= MOSTLY * len(amounts)
