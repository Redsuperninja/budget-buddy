"""Budget Buddy for Windows (roadmap 22, 22b; ADR-0008): the dashboard in its own window, and an
optional light tray icon that starts with Windows.

Three modes of one program (``Budget Buddy.exe``, or ``python -m budget_buddy_desktop`` while
developing):
- no options: show the tray icon (if it isn't showing yet) and open the window;
- ``--background``: tray icon only, for starting with Windows. Nothing else runs until you open it;
- ``--window``: the window. It starts the Home Base as its own program and uses it over its local
  address, like a browser would. The Home Base stops when this program ends.

This part never imports the server's code (docs/dev/conventions.md): it starts the Home Base program
and talks to it over HTTP.
"""

__version__ = "0.1.0"
