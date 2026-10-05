"""Share counts as whole millionths of a share (``shares_micro``), never floats.

``"1.5"`` shares is ``1_500_000``. Six decimal places covers fractional shares from brokers
(most use up to 6 or fewer).
"""

import re

from app.models.tax import SHARES_SCALE

_DECIMALS = len(str(SHARES_SCALE)) - 1  # 6
_SHARES_RE = re.compile(r"[0-9]+(\.[0-9]+)?")
MAX_SHARES_MICRO = 10**15  # a billion shares: far beyond any personal holding, inside int64


def shares_to_micro(text: str) -> int:
    """``"1.5"`` -> ``1_500_000``. Exact: rejects more than 6 decimal places, signs, and
    anything that isn't plain digits. Raises ``ValueError`` with a plain-English reason."""
    if not isinstance(text, str):
        raise TypeError(f"Expected a string, got {type(text).__name__}")
    text = text.strip()
    if len(text) > 40 or not _SHARES_RE.fullmatch(text):
        raise ValueError("Enter a number of shares like 10 or 2.5, without commas")
    whole, _, fraction = text.partition(".")
    fraction = fraction.rstrip("0")
    if len(fraction) > _DECIMALS:
        raise ValueError("Shares can have at most 6 decimal places")
    micro = int(whole) * SHARES_SCALE + int(fraction.ljust(_DECIMALS, "0"))
    if micro >= MAX_SHARES_MICRO:
        raise ValueError("That's too many shares")
    return micro


def micro_to_text(micro: int) -> str:
    """``1_500_000`` -> ``"1.5"``, ``2_000_000`` -> ``"2"``."""
    if isinstance(micro, bool) or not isinstance(micro, int):
        raise TypeError(f"Expected whole millionths of a share as an int, got {type(micro)}")
    sign = "-" if micro < 0 else ""
    whole, fraction = divmod(abs(micro), SHARES_SCALE)
    text = f"{whole}.{fraction:0{_DECIMALS}d}".rstrip("0").rstrip(".")
    return sign + text
