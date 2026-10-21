"""Outside links from the dashboard (About: user guide, privacy, licences) open in the default web
browser, never inside the app window. Only Budget Buddy's own pages on GitHub are allowed."""

import webbrowser
from urllib.parse import unquote, urlsplit

ALLOWED_HOST = "github.com"
ALLOWED_PATH = "/Redsuperninja/budget-buddy"


def is_allowed(url: object) -> bool:
    """True only for an https://github.com/Redsuperninja/budget-buddy address (or a page under it)."""
    if not isinstance(url, str) or len(url) > 500 or any(c.isspace() or ord(c) < 32 for c in url):
        return False
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "https" or parts.hostname != ALLOWED_HOST or port is not None:
        return False
    if parts.username or parts.password or "\\" in url:
        return False
    if any(seg in ("..", ".") for seg in unquote(parts.path).split("/")):
        return False
    return parts.path == ALLOWED_PATH or parts.path.startswith(ALLOWED_PATH + "/")


def open_link(url: object) -> bool:
    """Open ``url`` in the default browser if it is allowed. Returns whether it was opened."""
    if not is_allowed(url):
        return False
    return bool(webbrowser.open(url))


def same_page(current: object, dashboard_url: str) -> bool:
    """True while the window is still on the dashboard (same scheme, host and port)."""
    try:
        a, b = urlsplit(str(current)), urlsplit(dashboard_url)
        return (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)
    except ValueError:
        return False


class Api:
    """What the dashboard page may ask of the app window (pywebview's js_api). Only this."""

    def open_link(self, url):
        return open_link(url)
