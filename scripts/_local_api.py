"""A small client for the Home Base's this-computer-only API, shared by the helper scripts.

It sends the Origin header and the write token (X-CSRF-Token) the API asks for, fetches the token
once, and turns errors into plain-English messages. The token is a secret while the Home Base is
running: it is only held in memory here, never printed or written to a file.
"""

import json as jsonlib
import urllib.error
import urllib.request


class ApiError(Exception):
    """The Home Base refused or failed a request. ``str(error)`` is its plain-English reason."""

    def __init__(self, message: str, method: str = "", path: str = "") -> None:
        super().__init__(message)
        self.method = method
        self.path = path


class NotRunning(ApiError):
    """Nothing answered at the address, so the Home Base isn't running there."""


def _reason(exc: urllib.error.HTTPError) -> str:
    try:
        return (jsonlib.loads(exc.read()).get("error") or {}).get("message") or exc.reason
    except (ValueError, AttributeError):
        return exc.reason


class LocalApi:
    def __init__(self, base: str) -> None:
        self.base = base
        self._token: str | None = None

    def token(self) -> str:
        """The Home Base's write token (it changes every time the Home Base starts)."""
        if self._token is None:
            url = self.base + "/api/local/csrf-token"
            try:
                with urllib.request.urlopen(url, timeout=15) as response:
                    self._token = jsonlib.loads(response.read())["token"]
            except urllib.error.HTTPError as exc:
                raise ApiError(_reason(exc), "GET", "/api/local/csrf-token") from None
            except (urllib.error.URLError, OSError):
                raise NotRunning("The Home Base isn't running.") from None
        return self._token

    def call(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
        timeout: int = 15,
    ):
        """Send one request. ``json`` or ``body`` is the payload. Returns the decoded JSON."""
        if json is not None:
            body, content_type = jsonlib.dumps(json).encode(), "application/json"
        request = urllib.request.Request(self.base + path, data=body, method=method)
        request.add_header("Origin", self.base)  # local API: same-origin requests only
        if body is not None:
            request.add_header("Content-Type", content_type or "application/json")
        if method != "GET":
            request.add_header("X-CSRF-Token", self.token())
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise ApiError(_reason(exc), method, path) from None
        except (urllib.error.URLError, OSError):
            raise NotRunning("The Home Base isn't running.", method, path) from None
        return jsonlib.loads(raw) if raw else None

    def items(self, path: str) -> list:
        """A list route's rows (the API sends either a bare list or ``{"items": [...]}``)."""
        result = self.call("GET", path)
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return result

