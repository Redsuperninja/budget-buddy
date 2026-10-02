"""Money helpers. Budget Buddy stores every amount as whole cents (``int``), never floats."""

from decimal import Decimal, InvalidOperation


def dollars_to_cents(value: str | Decimal) -> int:
    """Turn a dollar amount like ``"12.34"`` or ``Decimal("-5.5")`` into cents (1234, -550).

    Exact: uses ``Decimal``, so there is no rounding. Rejects floats (they can't hold most cent
    values exactly), more than 2 decimal places, and anything that isn't a plain number.
    Thousands separators and currency symbols are not accepted; strip them first.
    """
    if isinstance(value, str):
        try:
            amount = Decimal(value.strip())
        except InvalidOperation:
            raise ValueError(f"Not a dollar amount: {value!r}") from None
    elif isinstance(value, Decimal):
        amount = value
    else:
        raise TypeError(f"Expected a string or Decimal, got {type(value).__name__}")

    if not amount.is_finite():
        raise ValueError(f"Not a dollar amount: {value!r}")
    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -2:
        raise ValueError(f"More than 2 decimal places: {value!r}")
    return int(amount.scaleb(2))


def cents_to_display(cents: int) -> str:
    """Format cents for people: ``123456`` -> ``"$1,234.56"``, ``-500`` -> ``"-$5.00"``."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise TypeError(f"Expected whole cents as an int, got {type(cents).__name__}")
    sign = "-" if cents < 0 else ""
    dollars, rest = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{rest:02d}"
