"""The one way Budget Buddy hashes a secret it must recognize but never keep (device tokens,
pairing and join codes, computer cookies): SHA-256 of the UTF-8 text, lowercase hex. These secrets
are long and random, so a plain hash is enough; compare hashes with ``hmac.compare_digest``."""

import hashlib


def hash_secret(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
