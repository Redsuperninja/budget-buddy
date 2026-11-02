"""The app window: the dashboard shown in a native window (pywebview, using Windows' built-in Edge
WebView2), and a plain message window when something goes wrong."""

import html
import logging
from pathlib import Path

from budget_buddy_desktop import links, navigation

log = logging.getLogger(__name__)
TITLE = "Budget Buddy"


def show_dashboard(url: str, storage_dir: Path) -> None:
    """Open the window on ``url`` and return when the user closes it.

    ``storage_dir`` keeps the window's own browser storage (the light/dark choice) between runs. The
    dashboard asks for nothing to be cached, so no financial data is written there.
    """
    import webview

    webview.settings["ALLOW_DOWNLOADS"] = True  # the tax summary's CSV download
    # Otherwise pywebview hands any new-window address to Windows unchecked; navigation.py handles those.
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    window = webview.create_window(
        TITLE, url, width=1200, height=820, min_size=(720, 520), js_api=links.Api()
    )

    def stay_on_dashboard() -> None:
        # Nothing should take the window to another site; if something did, go back.
        if not links.same_page(window.get_current_url(), url):
            window.load_url(url)

    # Backstop: navigation.guard cancels off-origin pages before they load; this catches anything else.
    window.events.loaded += stay_on_dashboard

    def guard_native() -> None:
        ok: list[bool] = []
        try:
            native = window.native
            navigation.on_ui_thread(native, lambda: ok.append(navigation.guard(native, url)))
            if not ok or not ok[0]:
                log.warning("No WebView2 control found; only the after-load check keeps the window on the dashboard")
        except Exception:  # the window stays usable; the loaded check above still applies
            log.exception("Could not attach the navigation guard")

    window.events.before_show += guard_native  # runs before the first page is requested
    webview.start(private_mode=False, storage_path=str(storage_dir))


def show_problem(message: str) -> None:
    """A small window with a plain-English message, for when Budget Buddy can't start."""
    import webview

    body = (
        "<body style='font-family:system-ui,sans-serif;padding:1.5rem;line-height:1.5'>"
        f"<h2>Budget Buddy couldn't start</h2><p>{html.escape(message)}</p>"
        "<p>Close this window to try again later.</p></body>"
    )
    webview.create_window(TITLE, html=body, width=560, height=320)
    webview.start()
