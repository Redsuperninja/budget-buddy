"""Strict base64url without padding (sync contract §4.6).

Binary values on the wire are canonical, unpadded base64url with exact lengths, so there is only
one valid text for any given bytes.
"""

import base64
import re

_B64U = re.compile(r"[A-Za-z0-9_-]*")


def b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_decode(text: object, expected_len: int | None = None) -> bytes:
    """Decode ``text`` or raise ``ValueError``. ``fullmatch`` so a trailing newline is refused."""
    if not isinstance(text, str) or not _B64U.fullmatch(text) or len(text) % 4 == 1:
        raise ValueError("not base64url")
    data = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    if b64u_encode(data) != text:
        raise ValueError("non-canonical base64url")
    if expected_len is not None and len(data) != expected_len:
        raise ValueError("wrong length")
    return data
