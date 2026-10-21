"""Fail if a tracked file holds something that must never be public: a secret, a real-looking email
address, a personal home-folder or network path, a public IP address, or a kind of file that holds
private data (`.env`, a database, a `.bbbackup`, a key, a bank file, a picture outside the image
folders, a file too big to check).

    python3 scripts/dev/check_public.py      (on Windows, type py)

Prints `file:line: [rule] reason` for each finding (never the value), exit 1.
Justified exceptions go in `scripts/dev/public_allowlist.txt` (format explained there). Part of
`check_all.py` and CI. This file builds its own patterns from pieces so they never match itself.
"""

import codecs
import fnmatch
import ipaddress
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ALLOWLIST = Path(__file__).with_name("public_allowlist.txt")
ALLOWLIST_REL = "scripts/dev/public_allowlist.txt"
MAX_BYTES = 2_000_000  # a bigger tracked file can't be checked by eye: it must be allowlisted

Finding = tuple[int, str, str, str]  # line, rule, reason, the matched text (for the allowlist)

# --- Emails ---------------------------------------------------------------------------------------
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b")
# Placeholder domains (and their subdomains), plus the no-reply addresses GitHub and git use.
# A `.local` name is not safe: it names a real computer.
SAFE_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "users.noreply.github.com")
SAFE_EMAIL_ENDINGS = (".example", ".test", ".invalid", ".localhost")
SAFE_EMAIL_LOCAL = re.compile(r"^(noreply|no-reply)$", re.I)
# `icon@2x.png`-style file names are not addresses.
FILE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "js", "ts", "json", "css", "html"}

# --- Paths with a user or computer name -----------------------------------------------------------
_SEP = r"[\\/]+"
_NAME = r"([^\\/\s\"'`:*<>|]+|<[^>\s]*>)"
HOME_PATH = re.compile(
    r"(?<![\w.-])(?:[A-Za-z]:"
    + _SEP
    + r"(?:Users|Documents and Settings)"
    + _SEP
    + r"|/Users/|/ho"
    + "me/)"
    + _NAME,
    re.I,
)
UNC_PATH = re.compile(r"(?<![\w\\])\\\\([A-Za-z0-9][A-Za-z0-9._-]*)\\[A-Za-z0-9$._-]")
PLACEHOLDER_NAME = re.compile(
    r"^(<.*>|\{.*\}|\$.*|%.*%|~.*|\.\.\.|x+|you|your[-_ ]?name|your[-_ ]?user(name)?|user(name)?|"
    r"me|name|example|test|public|default|runner|someone|foo|bar|host|server|localhost|"
    r"all users|defaultuser0)$",
    re.I,
)

# --- IP addresses ---------------------------------------------------------------------------------
IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\w])(?!\.\d)")
IPV6 = re.compile(r"(?<![\w:.])((?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4})(?![\w:.])")
DOC_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]
GLOBAL_V6 = ipaddress.ip_network("2000" + "::/3")  # public addresses all start here
VERSION_BEFORE = re.compile(r"(?i)(?:\b(?:version|ver|v)|==|~=|>=|<=|\^|~)\s*$")
# Dependency lock files are full of version numbers and hashes, not addresses.
IP_SKIP = ("package-lock.json", "requirements*.txt", "*.lock")

# --- Secrets inside text (pieces joined, so this file doesn't match its own patterns) -------------
SECRET_PATTERNS = [
    re.compile("-----" + "BEGIN [A-Z ]*PRIVATE" + " KEY[A-Z ]*-----"),
    re.compile(r"\bgh[pousr]" + r"_[A-Za-z0-9]{30,}"),
    re.compile(r"\bgithub" + r"_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"\bsk" + r"-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bAK" + r"IA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox" + r"[bpars]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAI" + r"za[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\b[sr]k" + r"_live_[0-9A-Za-z]{20,}"),
    re.compile(r"\bey" + r"J[A-Za-z0-9_-]{10,}\.ey" + r"J[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]

# --- File kinds (by name and place) ---------------------------------------------------------------
KEY_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".crt", ".cer", ".der", ".jks", ".keystore", ".p8"}
KEY_NAMES = {"id_rsa", "id_ed25519", "id_ecdsa", "id_dsa", "secrets.json", ".npmrc", ".netrc"}
DB_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".db3", ".sql", ".db-wal", ".db-shm"}
DB_SUFFIXES |= {".db-journal", ".sqlite-journal", ".sqlite-wal", ".sqlite-shm"}
STATEMENT_SUFFIXES = {".csv", ".ofx", ".qfx", ".qif", ".xlsx", ".xls"}
PICTURE_SUFFIXES = {".png", ".jpg", ".jpeg", ".jfif", ".gif", ".webp", ".bmp", ".heic", ".tif"}
PICTURE_SUFFIXES |= {".tiff", ".pdf", ".svg", ".ico", ".avif"}
SAFE_PICTURE_SUFFIXES = {".png", ".svg"}
IMAGE_DIRS = (
    "docs/guide/images/",
    "docs/showcase/images/",
    "mobile/assets/images/",
    "desktop/assets/",
    "dashboard/assets/",
    "assets/",
)


def tracked_files(repo: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=repo, capture_output=True, check=True)
    return [p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]


# --- Allowlist: `rule path-glob value  # reason` --------------------------------------------------
def load_allowlist(path: Path = ALLOWLIST) -> list[tuple[str, str, str]]:
    """(rule, path glob, exact value) triples. Name-based rules have no value (empty). Blank lines
    and `#` comments (a line starting with `#`, or text after two spaces and `#`) are ignored."""
    entries = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.split("  #", 1)[0].strip()
            if line and not line.startswith("#"):
                parts = line.split(None, 2)
                parts += [""] * (3 - len(parts))
                entries.append((parts[0], parts[1], parts[2].strip()))
    return entries


def is_allowed(rule: str, rel: str, value: str, allowlist: list[tuple[str, str, str]]) -> bool:
    return any(r == rule and v == value and fnmatch.fnmatch(rel, g) for r, g, v in allowlist)


# --- Text rules -----------------------------------------------------------------------------------
def email_is_real(match: re.Match) -> bool:
    domain = match.group(1).lower()
    local = match.group(0).split("@", 1)[0]
    if domain in SAFE_EMAIL_DOMAINS or domain.endswith(tuple("." + d for d in SAFE_EMAIL_DOMAINS)):
        return False
    if domain.endswith(SAFE_EMAIL_ENDINGS) or SAFE_EMAIL_LOCAL.match(local):
        return False
    return domain.rsplit(".", 1)[-1].lower() not in FILE_EXT


def ip_is_public(text: str, before: str) -> bool:
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return False  # not an address, like 999.1.1.1
    if ip.version == 6:
        return ip in GLOBAL_V6 and ip.is_global and not ip.is_multicast
    if not ip.is_global or ip.is_multicast or any(ip in net for net in DOC_NETS):
        return False
    return not VERSION_BEFORE.search(before)  # "version 1.2.3.4" is a version


def scan_text(rel: str, text: str) -> list[Finding]:
    """Findings in one file's text."""
    found: list[Finding] = []
    skip_ip = any(fnmatch.fnmatch(Path(rel).name, g) for g in IP_SKIP)
    for number, line in enumerate(text.splitlines(), 1):
        for pattern in SECRET_PATTERNS:
            for m in pattern.finditer(line):
                found.append((number, "secret", "a key, token or password", m.group(0)))
        for m in EMAIL.finditer(line):
            if email_is_real(m):
                found.append((number, "email", "an email address that looks real", m.group(0)))
        for m in HOME_PATH.finditer(line):
            if not PLACEHOLDER_NAME.match(m.group(1)):
                why = "a home-folder path with a real-looking user name"
                found.append((number, "home-path", why, m.group(0)))
        for m in UNC_PATH.finditer(line):
            if not PLACEHOLDER_NAME.match(m.group(1)):
                found.append((number, "home-path", "a network path naming a computer", m.group(0)))
        if not skip_ip:
            for pattern in (IPV4, IPV6):
                for m in pattern.finditer(line):
                    if ip_is_public(m.group(1), line[: m.start()]):
                        found.append((number, "ip", "a public IP address", m.group(1)))
    return found


def decode(data: bytes) -> str | None:
    """A file's text (UTF-8 or UTF-16, told apart by the BOM), or None if it is binary."""
    if data.startswith(codecs.BOM_UTF8):
        return data[3:].decode("utf-8", "replace")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", "replace")
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", "replace")


# --- File-kind rules ------------------------------------------------------------------------------
def scan_name(rel: str) -> list[tuple[str, str]]:
    """(rule, reason) for a file that should not be tracked at all, judged by name and place."""
    path = Path(rel)
    name, suffix = path.name.lower(), path.suffix.lower()
    if name == ".env" or (name.startswith(".env.") and name not in (".env.example", ".env.sample")):
        return [("env-file", "an .env file (it holds settings and secrets)")]
    if suffix in DB_SUFFIXES:
        return [("database", "a database, dump or journal file (it holds personal data)")]
    if suffix == ".bbbackup":
        return [("backup", "a Budget Buddy backup (it holds all your data)")]
    if suffix in KEY_SUFFIXES or name in KEY_NAMES:
        return [("key-file", "a key, certificate or credentials file")]
    if suffix in STATEMENT_SUFFIXES:
        return [("statement", "a spreadsheet or bank file (it could be real transactions)")]
    if suffix in PICTURE_SUFFIXES and not (
        suffix in SAFE_PICTURE_SUFFIXES and rel.startswith(IMAGE_DIRS)
    ):
        return [("image", "a picture or PDF outside the image folders (it could be a receipt)")]
    return []


def file_findings(repo: Path, rel: str) -> list[Finding]:
    hits: list[Finding] = [(0, rule, why, "") for rule, why in scan_name(rel)]
    file = repo / rel
    if not file.is_file():
        return hits
    if file.stat().st_size > MAX_BYTES:
        return hits + [(0, "too-big", "a file too big to check (over 2 MB)", "")]
    text = decode(file.read_bytes())
    if text is None:
        return hits
    if rel == ALLOWLIST_REL:
        # Only "rule path" is checked: the value and the reason are the very text it excuses.
        lines = [ln.split("  #", 1)[0] for ln in text.splitlines() if not ln.startswith("#")]
        text = "\n".join(" ".join(ln.split(None, 2)[:2]) for ln in lines)
    return hits + scan_text(rel, text)


def scan_repo(repo: Path = REPO, allowlist: list[tuple[str, str, str]] | None = None) -> list[str]:
    allowlist = load_allowlist() if allowlist is None else allowlist
    return [
        f"{rel}:{number}: [{rule}] {why}"
        for rel in tracked_files(repo)
        for number, rule, why, value in file_findings(repo, rel)
        if not is_allowed(rule, rel, value, allowlist)
    ]


def main() -> int:
    problems = scan_repo()
    for problem in problems:
        print(problem)
    if problems:
        print(
            f"\n{len(problems)} thing(s) that must not be public. Remove them, or if one is "
            "deliberate add it to scripts/dev/public_allowlist.txt with a reason."
        )
        return 1
    print("check_public: nothing private found in tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
