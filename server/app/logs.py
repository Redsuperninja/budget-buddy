"""Logging setup. Access logs never include query strings.

A query string can carry personal text, such as ``?q=pharmacy copay`` when searching transaction
descriptions, and the log must never contain descriptions (see the security rules). Each access-log
line keeps the method, path and status, which is all that's needed to see what happened.
"""

import copy
import logging
from typing import Any

from uvicorn.config import LOGGING_CONFIG


def strip_query(path: str) -> str:
    """``/api/local/transactions?q=x`` -> ``/api/local/transactions``."""
    return path.split("?", 1)[0]


class NoQueryStringFilter(logging.Filter):
    """Remove the query string from uvicorn access-log lines.

    uvicorn logs ``'%s - "%s %s HTTP/%s" %d'`` with the path (and query) as one argument. Any
    argument that looks like a path is cut at the ``?``. If a line still has a ``?`` after that
    (say a future uvicorn formats it differently), the line is dropped rather than leak.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                strip_query(arg) if isinstance(arg, str) and arg.startswith("/") else arg
                for arg in record.args
            )
        return "?" not in record.getMessage()


def log_config() -> dict[str, Any]:
    """uvicorn's default logging setup plus ``NoQueryStringFilter`` on the access log."""
    config = copy.deepcopy(LOGGING_CONFIG)
    config.setdefault("filters", {})["no_query_string"] = {"()": NoQueryStringFilter}
    config["loggers"]["uvicorn.access"]["filters"] = ["no_query_string"]
    return config
