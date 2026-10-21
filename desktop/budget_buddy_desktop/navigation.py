"""Keeps the app window on the dashboard (Windows, WebView2 through pywebview's native control).

Off-origin navigations are cancelled before they start, so an outside page never loads or runs script.
New-window requests (target=_blank, window.open) are handled here instead of by pywebview, which would pass
the address to the system unchecked: allowlisted GitHub pages open in the default browser through
``links.open_link`` and everything else is dropped.
"""

from budget_buddy_desktop import links


def on_navigation_starting(dashboard_url: str):
    def handler(_sender, args) -> None:
        if not links.same_page(str(args.Uri), dashboard_url):
            args.Cancel = True

    return handler


def on_new_window_requested(_sender, args) -> None:
    args.Handled = True  # nothing opens a window of its own
    links.open_link(str(args.Uri))  # dropped (False) unless it is a Budget Buddy GitHub page


def guard(native, dashboard_url: str) -> bool:
    """Attach the handlers to the window's WebView2 control. Returns False if the control isn't there
    (not WebView2); the page-loaded check in window.py still applies then."""
    webview = getattr(getattr(native, "browser", None), "webview", None)
    if webview is None:
        return False
    webview.NavigationStarting += on_navigation_starting(dashboard_url)

    def attach_core(*_args) -> None:
        core = webview.CoreWebView2
        if core is not None:
            core.NewWindowRequested += on_new_window_requested

    if getattr(webview, "CoreWebView2", None) is not None:
        attach_core()
    else:
        webview.CoreWebView2InitializationCompleted += attach_core
    return True
