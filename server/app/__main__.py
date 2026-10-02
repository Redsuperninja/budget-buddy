"""Run the Home Base with ``python -m app``."""

import uvicorn

from app.config import Settings
from app.main import create_app


def main() -> None:
    settings = Settings()
    # proxy_headers=False: never trust X-Forwarded-For, so the private-network check
    # always sees the real client address.
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, proxy_headers=False)


if __name__ == "__main__":
    main()
