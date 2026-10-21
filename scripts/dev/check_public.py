"""Fail if a tracked file holds something that must never be public: a real-looking email address,
a personal home-folder path, a public IP address, or a file kind that holds private data
(`.env`, a database, a `.bbbackup`, a key or certificate, a picture outside docs/ and assets/).

    python3 scripts/dev/check_public.py      (on Windows, type py)

Prints `file:line: [rule] reason` for each finding and exits 1. Justified exceptions go in
`scripts/dev/public_allowlist.txt` (format explained there). Part of `check_all.py` and CI.
"""

import fnmatch
import ipaddress
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ALLOWLIST = Path(__file__).with_name("public_allowlist.txt")
MAX_BYTES = 2_000_000  # bigger tracked files are not text we write by hand

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b")
# Placeholder domains (and their subdomains), plus the no-reply addresses GitHub and git use.
SAFE_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "users.noreply.github.com")
SAFE_EMAIL_ENDINGS = (".example", ".test", ".invalid", ".localhost", ".local")
SAFE_EMAIL_LOCAL = re.compile(r"^(noreply|no-reply)$", re.I)
# `icon@2x.png`-style file names are not addresses.
FILE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "js", "ts", "json", "css", "html"}

HOME_PATH = re.compile(r"(?<![\w.-])(?:[A-Za-z]:[\\/]+Users[\\/]+|/Users/|/home/)([^\\/\s\"'`:*]+)")
PLACEHOLDER_NAME = re.compile(
    r"^(<.*>|\{.*\}|\$.*|%.*%|~.*|\.\.\.|x+|you|your[-_ ]?name|your[-_ ]?user(name)?|user(name)?|"
    r"me|name|example|test|public|default|runner|someone|foo|bar)$",
    re.I,
)

IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\w])(?!\.\d)")
DOC_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]
VERSION_BEFORE = re.compile(r"(?i)(version|ver|v|==|~=|>=|<=|\^|~)\s*$")
# Dependency lock files are full of version numbers and hashes, not addresses.
IP_SKIP = ("package-lock.json", "requirements*.txt", "*.lock")

KEY_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".crt", ".cer", ".der", ".jks", ".keystore", ".p8"}
KEY_NAMES = {"id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"}
DB_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".db3", ".db-wal", ".db-shm"}
IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".heic",
    ".tif",
    ".tiff",
    ".pdf",
}
IMAGE_DIRS = ("docs/", "assets/", "mobile/assets/", "desktop/assets/", "dashboard/assets/")


def tracked_files(repo: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=repo, capture_output=True, check=True)
    return [p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]


def load_allowlist(path: Path = ALLOWLIST) -> list[tuple[str, str]]:
    """(rule, path glob) pairs; blank lines and `#` comments are ignored."""
    entries = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].strip()
            if line:
                rule, _, glob = line.partition(" ")
                entries.append((rule, glob.strip()))
    return entries


def is_allowed(rule: str, rel: str, allowlist: list[tuple[str, str]]) -> bool:
    return any(r == rule and fnmatch.fnmatch(rel, g) for r, g in allowlist)


def email_is_real(match: re.Match) -> bool:
    domain = match.group(1).lower()
    local = match.group(0).split("@", 1)[0]
    if domain in SAFE_EMAIL_DOMAINS or domain.endswith(tuple("." + d for d in SAFE_EMAIL_DOMAINS)):
        return False
    if domain.endswith(SAFE_EMAIL_ENDINGS) or SAFE_EMAIL_LOCAL.match(local):
        return False
    return domain.rsplit(".", 1)[-1] not in FILE_EXT


def ip_is_public(text: str, before: str) -> bool:
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return False  # not an address, like 999.1.1.1
    if not ip.is_global or ip.is_multicast or any(ip in net for net in DOC_NETS):
        return False
    return not VERSION_BEFORE.search(before)  # "version 1.2.3.4" is a version


def scan_text(rel: str, text: str) -> list[tuple[int, str, str]]:
    """(line, rule, reason) for each finding in one file's text."""
    found = []
    skip_ip = any(fnmatch.fnmatch(Path(rel).name, g) for g in IP_SKIP)
    for number, line in enumerate(text.splitlines(), 1):
        for m in EMAIL.finditer(line):
            if email_is_real(m):
                found.append((number, "email", "an email address that looks real"))
        for m in HOME_PATH.finditer(line):
            if not PLACEHOLDER_NAME.match(m.group(1)):
                found.append(
                    (number, "home-path", "a home-folder path with a real-looking user name")
                )
        if not skip_ip:
            for m in IPV4.finditer(line):
                if ip_is_public(m.group(1), line[: m.start()]):
                    found.append((number, "ip", "a public IP address"))
    return found


def scan_name(rel: str) -> list[tuple[str, str]]:
    """(rule, reason) for a file that should not be tracked at all, judged by name and place."""
    path = Path(rel)
    name, suffix = path.name.lower(), path.suffix.lower()
    if name == ".env" or (name.startswith(".env.") and name not in (".env.example", ".env.sample")):
        return [("env-file", "an .env file (it holds settings and secrets)")]
    if suffix in DB_SUFFIXES:
        return [("database", "a database file (it holds personal data)")]
    if suffix == ".bbbackup":
        return [("backup", "a Budget Buddy backup (it holds all your data)")]
    if suffix in KEY_SUFFIXES or name in KEY_NAMES:
        return [("key-file", "a key or certificate file")]
    if suffix in IMAGE_SUFFIXES and not rel.startswith(IMAGE_DIRS):
        return [("image", "a picture or PDF outside docs/ and assets/ (it could be a receipt)")]
    return []


def scan_repo(repo: Path = REPO, allowlist: list[tuple[str, str]] | None = None) -> list[str]:
    allowlist = load_allowlist() if allowlist is None else allowlist
    problems = []
    for rel in tracked_files(repo):
        hits = [(0, rule, why) for rule, why in scan_name(rel)]
        file = repo / rel
        if file.is_file() and file.stat().st_size <= MAX_BYTES:
            data = file.read_bytes()
            if b"\0" not in data[:8192]:  # skip binary files
                hits += scan_text(rel, data.decode("utf-8", "replace"))
        problems += [
            f"{rel}:{number}: [{rule}] {why}"
            for number, rule, why in hits
            if not is_allowed(rule, rel, allowlist)
        ]
    return problems


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
