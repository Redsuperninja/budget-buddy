"""Run the Home Base with ``python -m app``.

Also: ``python -m app recovery-phrase show|restore`` (see ``app/cli.py``).
"""

import sys

import uvicorn

from app.config import Settings
from app.logs import log_config
from app.main import create_app


def serve() -> None:
    settings = Settings()
    # proxy_headers=False: never trust X-Forwarded-For, so the private-network check
    # always sees the real client address. log_config: access logs leave out query strings.
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        proxy_headers=False,
        log_config=log_config(),
    )


def main() -> None:
    from app.cli import main as cli_main

    sys.exit(cli_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
