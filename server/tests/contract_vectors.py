"""The sync contract's published test vectors (section 4.7). Fake keys and data only.

Shared so the pairing and sync tests check the same bytes. Tests using them live in
tests/devices/test_envelope_vectors.py.
"""

from app.crypto.b64url import b64u_decode

KEY = b64u_decode("AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8", 32)
V1 = {
    "v": 1,
    "nonce": "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3",
    "ts": 1790000000,
    "box": (
        "h3tnJpseU-mZcMCYFrdbMYp7Odw9QnisK0cwHy5klYDKkIe6xiATRIxGA6LyN46Q0n-4rJ-LQ-3zIQDf1_FcItKiw"
        "usyFNue2TJQ6OB3Ly7bIX6xJfqbUjm4RRhuulXPJek3maWpfGGPCQ12_-DORKg"
    ),
}
V2 = {
    "v": 1,
    "nonce": "QEFCQ0RFRkdISUpLTE1OT1BRUlNUVVZX",
    "ts": 1790000001,
    "box": (
        "hlFMv8abBA-l4oJaaRR4wDE1IQBKNJkQ5CsUEkqleIW9FXxlWnpv-NTlEvrI9aEmsRZTM6f0g20QNU0Ve5s5QMvnTB"
        "_rzYAzxKj6ykod04XRmOGWeePezi-F5XD-bD8BYnJcPJt9bVe9XcBjvFOnpeuQUTyfJAe-DC--kT6NYdUvBUQi5_an"
        "PPrja69GQjnA3ZUMVuf2DQ"
    ),
}

PAIR_SK = bytes(range(0xA0, 0xC0))
VECTOR_CODE = "pQ3mX9vT2aLk8RzN1bWc4g"
VECTOR_PHONE_PUB = "ST6C_HRGSlkmiBdiPSBTxeuOLMSpiLT-4XnsawENUx0"
VECTOR_BODY = {
    "v": 1,
    "nonce": "wMHCw8TFxsfIycrLzM3Oz9DR0tPU1dbX",
    "ts": 1790000000,
    "phone_pub": VECTOR_PHONE_PUB,
    "box": (
        "iX68iqmvSCofJGxoNa6ebGX424xYOa65Hp175w4pshg0QFxkfGk7IJSqHtBmtUmvZqsuM3uzkXYBVTevNr3Pt8LZmisOoF1RHF7b"
        "cQ1d01XIRobOmjXEr5AKOoJ9Gip52s6weSGEDbLZYnq9dE0HaO4Hb475qcwAQ_hrx_EpnEXBfJatjlr-W3-1-1XYBTtN9dOC9U12"
        "WfqBH76uDT23FI_1BTze3vUIbT3lBerNaXkQflETufHrnpuhaIUEeVvJzNi_A-2QmCAH"
    ),
}
