"""Money helpers. Budget Buddy stores every amount as whole cents (``int``), never floats."""

import re
from decimal import Decimal

# Plain ASCII digits with an optional sign and decimal part, as people type them: "12.34", "12.",
# ".50". No exponents, underscores, thousands separators, currency symbols, or non-ASCII digits,
# and never a bare "." or "-.".
_AMOUNT_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)")
_CENT = Decimal("0.01")
MAX_ABS_CENTS = 10**13  # $100 billion: far beyond any personal amount, well inside int64


def dollars_to_cents(value: str | Decimal) -> int:
    """Turn a dollar amount like ``"12.34"``, ``".50"`` or ``Decimal("-5.5")`` into cents (1234, 50,
    -550).

    Exact: uses ``Decimal``, so there is no rounding. Extra trailing zeros are fine (``"1.500"``),
    but fractions of a cent (``"1.005"``) are rejected. Floats are rejected because they can't
    hold most cent values exactly. Bad input always raises ``ValueError`` (or ``TypeError`` for
    the wrong type), never another arithmetic error.
    """
    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"Not a dollar amount: {value!r}")
        if value.adjusted() > 20:  # don't spell out an enormous number just to reject it
            raise ValueError(f"Dollar amount is too large: {value!r}")
        text = format(value, "f")
    else:
        raise TypeError(f"Expected a string or Decimal, got {type(value).__name__}")

    if not _AMOUNT_RE.fullmatch(text):
        raise ValueError(f"Not a dollar amount: {value!r}")
    amount = Decimal(text)
    # Check the size before quantize(), which would raise InvalidOperation on huge numbers.
    if abs(amount) >= Decimal(MAX_ABS_CENTS) / 100:
        raise ValueError(f"Dollar amount is too large: {value!r}")
    if amount != amount.quantize(_CENT):
        raise ValueError(f"Amount has fractions of a cent (more than 2 decimal places): {value!r}")
    return int(amount.scaleb(2))


def cents_to_display(cents: int) -> str:
    """Format cents for people: ``123456`` -> ``"$1,234.56"``, ``-500`` -> ``"-$5.00"``."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise TypeError(f"Expected whole cents as an int, got {type(cents).__name__}")
    sign = "-" if cents < 0 else ""
    dollars, rest = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{rest:02d}"
