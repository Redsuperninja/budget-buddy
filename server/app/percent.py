"""Percentages as whole basis points (1% = 100 bp, 100% = 10,000 bp), so budget shares never use
floats. Results are rounded to the nearest cent or basis point, halves away from zero."""

WHOLE_BP = 10_000


def _round_div(numerator: int, denominator: int) -> int:
    """``numerator / denominator`` rounded to the nearest whole number, halves away from zero."""
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return quotient if numerator >= 0 else -quotient


def share_of(cents: int, bp: int) -> int:
    """``bp`` basis points of ``cents``: ``share_of(400_000, 1_500)`` is 60_000 (15% of $4,000)."""
    return _round_div(cents * bp, WHOLE_BP)


def percent_bp(part: int, whole: int) -> int | None:
    """``part`` as basis points of ``whole``, or None when ``whole`` isn't positive."""
    if whole <= 0:
        return None
    return _round_div(part * WHOLE_BP, whole)
