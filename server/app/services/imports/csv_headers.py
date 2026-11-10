"""Finding columns by the names in a CSV's header row, for imports with no column picker (stock
trades, positions). The bank import guesses its own way (``csv_columns``)."""

import re
from collections.abc import Callable

from app.errors import ApiError
from app.services.imports.csv_columns import detect_date_format

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


def find_header(
    rows: list[list[str]], pick: Callable[[list[str]], dict | None], no_columns: str
) -> tuple[int, dict]:
    """The first header row (within ``HEADER_SEARCH_ROWS``) that ``pick`` accepts, and its columns.
    Raises the "columns not found" error with ``no_columns`` as its message when none does."""
    for index, row in enumerate(rows[:HEADER_SEARCH_ROWS]):
        picked = pick([header_name(c) for c in row])
        if picked:
            return index, picked
    raise ApiError(422, "columns_not_found", no_columns)


def date_format_below(rows: list[list[str]], header_index: int, date_column: int) -> str:
    """The date format used in the cells under the header's date column."""
    dates = [r[date_column] for r in rows[header_index + 1 :] if date_column < len(r)]
    return detect_date_format(dates)
