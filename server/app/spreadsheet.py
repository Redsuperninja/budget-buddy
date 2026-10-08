"""Keeping text safe for spreadsheets ("CSV injection")."""

# A spreadsheet may run a cell that starts with one of these as a formula.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def formula_safe(text: str) -> str:
    """Put a leading apostrophe on text a spreadsheet could run as a formula."""
    return "'" + text if text.startswith(FORMULA_STARTS) else text
