"""Run the Home Base with ``python -m app``.

Also: ``python -m app recovery-phrase show|restore`` and ``backup make|restore`` (``app/cli.py``).
"""

import os
import sys

from app.config import Settings
from app.parent_watch import stop_when_gone
from app.serving import build_server, local_url


def serve() -> None:
    settings = Settings()
    server = build_server(settings)
    if settings.stop_with_pid:

        def stop() -> None:
            server.should_exit = True

        stop_when_gone(settings.stop_with_pid, stop)
    print(f"Budget Buddy is starting. Open {local_url(settings)} in your browser.", flush=True)
    server.run()


def _give_output_somewhere() -> None:
    """A windowed build (the desktop app's Home Base) has no console; logging needs one."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")  # noqa: SIM115 (lives as long as the process)
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")  # noqa: SIM115


def main() -> None:
    from app.cli import main as cli_main

    _give_output_somewhere()
    sys.exit(cli_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
