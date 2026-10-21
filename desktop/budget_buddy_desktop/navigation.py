"""Keeps the app window on the dashboard (Windows, WebView2 through pywebview's native control).

Off-origin navigations are cancelled before they start, so an outside page never loads or runs script.
New-window requests (target=_blank, window.open) are handled here instead of by pywebview, which would pass
the address to the system unchecked: allowlisted GitHub pages open in the default browser through
``links.open_link`` and everything else is dropped.
"""

import logging

from budget_buddy_desktop import links

log = logging.getLogger(__name__)


def on_navigation_starting(dashboard_url: str):
    def handler(_sender, args) -> None:
        if not links.same_page(str(args.Uri), dashboard_url):
            args.Cancel = True

    return handler


def on_new_window_requested(_sender, args) -> None:
    args.Handled = True  # nothing opens a window of its own
    links.open_link(str(args.Uri))  # dropped (False) unless it is a Budget Buddy GitHub page


def on_ui_thread(native, work) -> None:
    """Run ``work`` on the window's UI thread: WebView2 objects can only be touched there. pywebview's
    ``before_show`` handlers already run on it; this makes sure when they don't."""
    if getattr(native, "InvokeRequired", False):
        from System import Func, Type  # noqa: PLC0415 (pythonnet, Windows only)

        native.Invoke(Func[Type](lambda: work()))
    else:
        work()


def guard(native, dashboard_url: str) -> bool:
    """Attach the handlers to the window's WebView2 control. Returns False if the control isn't there
    (not WebView2); the page-loaded check in window.py still applies then."""
    webview = getattr(getattr(native, "browser", None), "webview", None)
    if webview is None:
        return False
    webview.NavigationStarting += on_navigation_starting(dashboard_url)
    log.info("Navigation guard attached: off-origin pages are cancelled before they load")

    def attach_core(*_args) -> None:
        core = webview.CoreWebView2
        if core is not None:
            core.NewWindowRequested += on_new_window_requested
            log.info("New-window guard attached: only Budget Buddy GitHub links open, in the browser")

    # The initialised event fires on the UI thread; if WebView2 is already up, attach on it too.
    webview.CoreWebView2InitializationCompleted += attach_core
    if getattr(webview, "CoreWebView2", None) is not None:
        attach_core()
    return True
