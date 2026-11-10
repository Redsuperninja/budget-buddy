"""The one place that asks the system clock for the date or time.

Everything stored is naive UTC; "today" is this computer's own date. Code calls
``clock.today()`` / ``clock.utcnow_naive()`` (not ``dt.date.today()``) so a test can freeze
them with one ``monkeypatch.setattr``.
"""

import datetime as dt


def today() -> dt.date:
    """This computer's date."""
    return dt.date.today()  # noqa: DTZ011 (the user's own local date, on purpose)


def utcnow_naive() -> dt.datetime:
    """Now in UTC with no time-zone marker, the form every stored timestamp uses."""
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)
