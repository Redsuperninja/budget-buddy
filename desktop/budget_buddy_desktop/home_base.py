"""Running the Home Base for the window: as its own program, used over its local address (ADR-0008).

It gets this app's process ID (``BUDGET_BUDDY_STOP_WITH_PID``), so it shuts itself down cleanly
about a second after this app ends, even if this app crashes. Its output is kept in memory (the last
few lines only) so a start-up problem can be shown in plain English; nothing is written to disk.
"""

import os
import subprocess
import sys
import threading
import time
from collections import deque

from budget_buddy_desktop import genuine, probe
from budget_buddy_desktop.commands import home_base_command

START_TIMEOUT_SECONDS = 60
GENERAL_PROBLEM = "Something unexpected stopped Budget Buddy from starting. Please try again."


class StartFailed(Exception):
    """The Home Base didn't start. The message is plain English for a dialog."""


def explain(lines: list[str], port: int) -> str:
    """Turn the Home Base's last output into a message for people."""
    text = "\n".join(lines)
    if "10048" in text or "address already in use" in text.lower() or "attempting to bind" in text:
        return (
            f"Budget Buddy couldn't use port {port}. Another program may be using it. Close that "
            "program, or restart the computer, and try again."
        )
    if any(line.startswith("Traceback") for line in lines):
        return GENERAL_PROBLEM
    last = next((line.strip() for line in reversed(lines) if line.strip()), "")
    # The Home Base's own start-up errors (key, database, data folder) are already plain English.
    return last if last and ":" not in last.split(" ", 1)[0] else GENERAL_PROBLEM


class HomeBase:
    def __init__(self, port: int) -> None:
        self.port = port
        self.url = probe.local_url(port)
        self.output: deque[str] = deque(maxlen=20)
        self.process: subprocess.Popen | None = None
        # True when Budget Buddy was already running (say, from the launch folder) and this window
        # uses it. It keeps running after the window closes.
        self.reused = False

    def start(self) -> None:
        if probe.is_running(self.port, timeout=0.5):
            # Only a Home Base that proves it's Budget Buddy is shown: anything else on the port
            # could be a look-alike collecting data.
            if genuine.is_budget_buddy(self.port):
                self.reused = True
                return
            raise StartFailed(
                f"Something else is using port {self.port}, so Budget Buddy can't start safely. "
                "Close the program using it, or restart the computer, and try again."
            )
        env = {**os.environ, "BUDGET_BUDDY_STOP_WITH_PID": str(os.getpid())}
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.process = subprocess.Popen(
            home_base_command(),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="replace",
            creationflags=flags,
        )
        threading.Thread(target=self._keep_last_lines, daemon=True).start()
        deadline = time.monotonic() + START_TIMEOUT_SECONDS
        while not self._ready():
            if self.process.poll() is not None:
                time.sleep(0.2)  # let the last lines arrive
                raise StartFailed(explain(list(self.output), self.port))
            if time.monotonic() > deadline:
                self.process.kill()
                raise StartFailed("Budget Buddy took too long to start. Please try again.")
            time.sleep(0.1)

    def _ready(self) -> bool:
        """Our own Home Base is still running and answering."""
        return self.process.poll() is None and probe.is_running(self.port, timeout=0.5)

    def _keep_last_lines(self) -> None:
        for line in self.process.stdout:  # also keeps the pipe from filling up
            self.output.append(line.rstrip("\n"))
