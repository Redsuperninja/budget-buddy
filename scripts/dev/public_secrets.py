"""Secret shapes for check_public.py: well-known token formats, and a quoted value after a name like
`api_key=` or `password:`. Patterns are built from pieces so this file never matches itself."""

import re

KNOWN = [
    re.compile("-----" + "BEGIN [A-Z ]*PRIVATE" + " KEY[A-Z ]*-----"),
    re.compile(r"\bgh[pousr]" + r"_[A-Za-z0-9]{30,}"),
    re.compile(r"\bgithub" + r"_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"\bglp" + r"at-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bnp" + r"m_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bpyp" + r"i-AgE[A-Za-z0-9_-]{50,}"),
    re.compile(r"\bsk" + r"-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"\b[sr]k" + r"_(?:live|test)_[0-9A-Za-z]{20,}"),
    re.compile(r"\b(?:AK|AS)" + r"IA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)aws_?secret_?(?:access_?)?key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}\b"),
    re.compile(r"\bxox" + r"[bpars]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAI" + r"za[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bey" + r"J[A-Za-z0-9_-]{10,}\.ey" + r"J[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]

# name = "value" with a value of 16+ characters (also `"X-Finnhub-Token": "value"`).
GENERIC = re.compile(
    r"""(?i)\b[\w-]*(?:api[_-]?key|token|secret|passw(?:or)?d)[\w-]*["']?\s*[:=]\s*["']([^"'\s]{16,})["']"""
)
# A value that is plainly a stand-in, not a real secret.
PLACEHOLDER = re.compile(
    r"(?i)your|x{4}|<|>|\{|\}|\$|%|example|placeholder|change[-_]?me|fake|dummy|sample|demo|test"
    r"|\*{3}|\.{3}|-here|redacted|secret|password|token|(.)\1{7}"
)


def secrets_in(line: str) -> list[str]:
    """The secret-looking texts on one line."""
    found = [m.group(0) for pattern in KNOWN for m in pattern.finditer(line)]
    for m in GENERIC.finditer(line):
        if not PLACEHOLDER.search(m.group(1)):
            found.append(m.group(1))
    return found
