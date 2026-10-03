"""Recovery phrase: the master key written out so a person can copy it onto paper.

Format: 64 characters in 16 groups of 4, like ``7K3M-Q9XA-...``. The characters encode 40 bytes:

    version (1 byte) | master key (32 bytes) | checksum (first 7 bytes of SHA-256 of the above)

using Crockford's Base32 alphabet (digits and capital letters without I, L, O, U). Why this and
not 24 words:

- Nothing to bundle or translate. A word list would add a 2,048-word file that must never change.
- Hard to misread: there's no I/L/1 or O/0 confusion, and on input lowercase, spaces, dashes,
  and the look-alike letters I, L, O are accepted and corrected automatically.
- The 56-bit checksum catches typos, swapped characters, and missing groups with near
  certainty, so a mistyped phrase is rejected instead of silently restoring the wrong key.
"""

import hashlib
import hmac

from app.crypto.errors import RecoveryPhraseError
from app.crypto.keys import MASTER_KEY_BYTES

PHRASE_VERSION = 0x01
CHECKSUM_BYTES = 7
GROUP_SIZE = 4
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DECODE = {ch: i for i, ch in enumerate(_ALPHABET)}
_DECODE.update({"O": 0, "I": 1, "L": 1})
_PAYLOAD_BYTES = 1 + MASTER_KEY_BYTES + CHECKSUM_BYTES  # 40 bytes = 320 bits = 64 characters
PHRASE_CHARS = _PAYLOAD_BYTES * 8 // 5


def _checksum(body: bytes) -> bytes:
    return hashlib.sha256(body).digest()[:CHECKSUM_BYTES]


def _b32encode(data: bytes) -> str:
    number = int.from_bytes(data, "big")
    chars = len(data) * 8 // 5
    return "".join(_ALPHABET[(number >> (5 * (chars - 1 - i))) & 31] for i in range(chars))


def master_key_to_phrase(master_key: bytes) -> str:
    if len(master_key) != MASTER_KEY_BYTES:
        raise ValueError("Master key must be 32 bytes.")
    body = bytes([PHRASE_VERSION]) + master_key
    text = _b32encode(body + _checksum(body))
    return "-".join(text[i : i + GROUP_SIZE] for i in range(0, len(text), GROUP_SIZE))


def phrase_to_master_key(phrase: str) -> bytes:
    """Read a recovery phrase back into the master key. Raises :class:`RecoveryPhraseError`."""
    cleaned = "".join(ch for ch in phrase.upper() if not ch.isspace() and ch != "-")
    if len(cleaned) != PHRASE_CHARS:
        raise RecoveryPhraseError(
            f"A recovery phrase has {PHRASE_CHARS} letters and numbers (16 groups of 4), but "
            f"that one has {len(cleaned)}. Please check it and try again."
        )
    number = 0
    for position, ch in enumerate(cleaned, start=1):
        if ch not in _DECODE:
            raise RecoveryPhraseError(
                f"Character {position} ({ch!r}) can't be in a recovery phrase. "
                "Please check it and try again."
            )
        number = (number << 5) | _DECODE[ch]
    payload = number.to_bytes(_PAYLOAD_BYTES, "big")
    body, check = payload[:-CHECKSUM_BYTES], payload[-CHECKSUM_BYTES:]
    if not hmac.compare_digest(check, _checksum(body)):
        raise RecoveryPhraseError(
            "That recovery phrase has a typo somewhere (its built-in check doesn't match). "
            "Please compare it with your saved copy, group by group, and try again."
        )
    if body[0] != PHRASE_VERSION:
        raise RecoveryPhraseError(
            "That recovery phrase is from a newer version of Budget Buddy. Please update first."
        )
    return body[1:]
