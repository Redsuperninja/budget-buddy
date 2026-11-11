"""Does a credit card OFX file list charges the wrong way round (as positive numbers)?

OFX says money out is negative, for cards too, and most issuers follow it. Some don't. The bank's
own ``TRNTYPE`` is the best clue: a DEBIT (a charge) with a positive amount, or a CREDIT (a
payment or refund) with a negative one, is backwards. The same check as the CSV card import
(``card_signs.looks_flipped``) also runs, and the file is flagged if either says backwards. The
types only count with at least ``MIN_TYPED_ROWS`` typed rows. The import never flips on its own:
the user chooses.
"""

from app.services.imports.card_signs import looks_flipped
from app.services.imports.ofx_parsing import OfxTransaction

MIN_TYPED_ROWS = 3  # fewer typed rows than this are too few to trust

FLIPPED = (
    "This card's file lists charges as positive numbers, the other way round from Budget Buddy "
    "(charges are money out, payments money in). Imported as they are, your purchases would "
    "count as money in. Choose whether to flip them before importing."
)


def _types_say_backwards(transactions: list[OfxTransaction]) -> bool:
    typed = [t for t in transactions if t.cents and t.trntype in ("DEBIT", "CREDIT")]
    if len(typed) < MIN_TYPED_ROWS:
        return False
    backwards = sum((t.trntype == "DEBIT") == (t.cents > 0) for t in typed)
    return backwards * 2 > len(typed)


def file_looks_flipped(transactions: list[OfxTransaction]) -> bool:
    """Flag the file when either check says backwards: a needless flag costs the user one choice."""
    return _types_say_backwards(transactions) or looks_flipped(
        [(t.description, t.cents) for t in transactions]
    )
