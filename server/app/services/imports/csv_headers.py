"""Finding columns by the names in a CSV's header row, for imports with no column picker (stock
trades, positions). The bank import guesses its own way (``csv_columns``)."""

import re

HEADER_SEARCH_ROWS = 10


def header_name(text: str) -> str:
    """Lower case letters and single spaces only: "Cost Basis Total ($)" -> "cost basis total"."""
    return " ".join(re.sub(r"[^a-z]", " ", text.casefold()).split())


def pick_columns(
    names: list[str],
    words: dict[str, tuple[str, ...]],
    avoid: dict[str, tuple[str, ...]] | None = None,
    required: set[str] | None = None,
    picked: dict | None = None,
) -> dict | None:
    """``{role: column}`` from ``header_name``s. Roles are matched in order, each with its words
    in order; a column is used once and never for a role whose ``avoid`` words it contains. None
    if a ``required`` role (all of them, by default) has no column. ``picked`` starts the result."""
    picked = dict(picked or {})
    required = set(words) if required is None else required
    for role, role_words in words.items():
        usable = [
            i
            for i, n in enumerate(names)
            if i not in picked.values() and not any(w in n for w in (avoid or {}).get(role, ()))
        ]
        col = next((i for w in role_words for i in usable if w in names[i]), None)
        if col is not None:
            picked[role] = col
        elif role in required:
            return None
    return picked
