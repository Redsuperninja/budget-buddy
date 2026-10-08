"""Start with Windows: an entry under the current user's Run key that starts the tray only.

No admin rights and no Windows service: it's the same list as "Startup apps" in Windows Settings,
where it can also be turned off. ``registry`` is the ``winreg`` module, passed in so tests can
fake it.
"""

from budget_buddy_desktop.commands import command_line

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Budget Buddy"


def _winreg():
    import winreg

    return winreg


def is_enabled(registry=None) -> bool:
    reg = registry or _winreg()
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY) as key:
            reg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool, registry=None) -> None:
    reg = registry or _winreg()
    with reg.CreateKey(reg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if on:
            reg.SetValueEx(key, VALUE_NAME, 0, reg.REG_SZ, command_line("--background"))
        else:
            try:
                reg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
