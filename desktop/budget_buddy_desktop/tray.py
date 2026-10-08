"""The tray icon: light until opened. No Home Base, database or keys run until the window opens.

Menu: Open Budget Buddy (also a double-click on the icon), a status line saying whether phones can
sync right now, Start with Windows (on/off), and Quit (closes the icon; an open window keeps running
until it's closed).
"""

from budget_buddy_desktop import autostart, commands, probe
from budget_buddy_desktop.icon import make_icon


class Tray:
    def __init__(self, port: int) -> None:
        self.port = port
        self.window = None  # the window process started from here, if any

    def open_window(self, icon=None, _item=None) -> None:
        if self.window is not None and self.window.poll() is None:
            if icon is not None:
                icon.notify("Budget Buddy is already open. Look for it in the taskbar.")
            return
        self.window = commands.spawn("--window")

    def status(self, _item=None) -> str:
        if probe.is_running(self.port, timeout=0.3):
            return "Running: phones can sync now"
        return "Resting: open it to let phones sync"

    @staticmethod
    def toggle_autostart(_icon=None, _item=None) -> None:
        autostart.set_enabled(not autostart.is_enabled())

    def run(self, open_now: bool) -> None:  # pragma: no cover (draws on screen; checked by hand)
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem("Open Budget Buddy", self.open_window, default=True),
            pystray.MenuItem(self.status, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Start with Windows",
                self.toggle_autostart,
                checked=lambda _item: autostart.is_enabled(),
            ),
            pystray.MenuItem("Quit", lambda icon, _item: icon.stop()),
        )
        icon = pystray.Icon("budget-buddy", make_icon(64), "Budget Buddy", menu)
        if open_now:
            self.open_window()
        icon.run()
