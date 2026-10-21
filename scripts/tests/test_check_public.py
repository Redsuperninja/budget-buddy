"""scripts/dev/check_public.py: what it flags, what it lets through, and the allowlist."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dev"))

import check_public as cp  # noqa: E402

# Sample "real" values are built from parts so this file doesn't trip the check itself.
USER = "ali" + "ce"
WIN = "C:" + "\\Users\\"
IP4 = ".".join(["8", "8", "8", "8"])
IP6 = "2001:" + "4860:4860::8888"
PEM = "-----" + "BEGIN RSA PRIVATE" + " KEY-----"
TOKENS = [
    "gh" + "p_" + "a1B2" * 9,
    "github" + "_pat_" + "a1B2_" * 10,
    "s" + "k-" + "proj-" + "abcDEF123456" * 3,
    "AK" + "IA" + "ABCDEFGHIJKLMNOP",
    "xo" + "xb-" + "1234567890-abcdef",
    "AI" + "za" + "A" * 35,
]


def rules(text, rel="a.md"):
    return [f[1] for f in cp.scan_text(rel, text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail bob@" + "gmail.com now", ["email"]),
        ("bob@example.com, x@y.example.org, noreply@github.com", []),
        ("12345+me@users.noreply.github.com", []),
        ("see icon@2x.png", []),
        ("bob@" + "MYPC.local", ["email"]),
        (WIN + USER + "\\Documents", ["home-path"]),
        (WIN.lower() + USER, ["home-path"]),
        ("C:" + "\\Documents and Settings\\" + USER, ["home-path"]),
        ("/Users/" + USER + "/x and /home/" + USER, ["home-path", "home-path"]),
        ("\\\\" + "OFFICEPC\\share", ["home-path"]),
        (WIN + "<you>\\x, /home/YOUR_NAME/x, /Users/example/x, C:\\Users\\Public", []),
        ("\\\\<host>\\share and \\\\localhost\\c$", []),
        ("import ./screens/home/home.js and a/Users/", []),
        ("host " + IP4, ["ip"]),
        ("addr " + IP6, ["ip"]),
        ("::1 fe80::1 fd12:3456::1 2001:db8::1 12:30:45 aa:bb:cc:dd:ee:ff", []),
        ("192.168.1.2 10.0.0.1 127.0.0.1 0.0.0.0 203.0.113.7 198.51.100.1 192.0.2.4", []),
        ("version " + IP4 + " and pkg==" + IP4 + " and v" + IP4, []),
        ("dev " + IP4, ["ip"]),
        ("999.1.1.1 and 1.2.3", []),
        (PEM, ["secret"]),
        ("password is fine here", []),
    ],
)
def test_scan_text(text, expected):
    assert rules(text) == expected


@pytest.mark.parametrize("token", TOKENS)
def test_secret_tokens(token):
    assert rules(f'key = "{token}"') == ["secret"]


def test_lock_files_skip_ip_check():
    assert rules("x " + IP4, "requirements.txt") == []


@pytest.mark.parametrize(
    ("rel", "expected"),
    [
        (".env", ["env-file"]),
        ("server/.env.local", ["env-file"]),
        (".env.example", []),
        ("data/budget.db", ["database"]),
        ("x/y.sqlite3", ["database"]),
        ("x/dump.sql", ["database"]),
        ("x/a.db-journal", ["database"]),
        ("x/a.sqlite-journal", ["database"]),
        ("backups/a.bbbackup", ["backup"]),
        ("certs/server.pem", ["key-file"]),
        ("id_rsa", ["key-file"]),
        ("config/secrets.json", ["key-file"]),
        ("mobile/.npmrc", ["key-file"]),
        ("a/statement.csv", ["statement"]),
        ("a/b.OFX", ["statement"]),
        ("a/b.qif", ["statement"]),
        ("a/b.xlsx", ["statement"]),
        ("receipts/r1.jpg", ["image"]),
        ("a/r.jfif", ["image"]),
        ("a/scan.pdf", ["image"]),
        ("docs/scan.pdf", ["image"]),
        ("docs/photo.jpg", ["image"]),
        ("docs/stray/shot.png", ["image"]),
        ("mobile/assets/images/icon.png", []),
        ("docs/guide/images/home.png", []),
        ("dashboard/app.css", []),
    ],
)
def test_scan_name(rel, expected):
    assert [rule for rule, _ in cp.scan_name(rel)] == expected


def test_decode_by_bom():
    assert "hi" in cp.decode("hi".encode("utf-16"))
    assert cp.decode(b"\xef\xbb\xbfhi") == "hi"
    assert cp.decode(b"\x89PNG\x00\x01") is None


def test_allowlist_parsing_and_matching(tmp_path):
    f = tmp_path / "allow.txt"
    f.write_text(
        "# note\n\nip docs/*.md 203.0.113.5  # why\ndatabase x.db  # no value\n", encoding="utf-8"
    )
    allow = cp.load_allowlist(f)
    assert allow == [("ip", "docs/*.md", "203.0.113.5"), ("database", "x.db", "")]
    assert cp.is_allowed("ip", "docs/a.md", "203.0.113.5", allow)
    assert not cp.is_allowed("ip", "docs/a.md", "203.0.113.6", allow)  # only that value
    assert not cp.is_allowed("email", "docs/a.md", "203.0.113.5", allow)
    assert not cp.is_allowed("ip", "src/a.md", "203.0.113.5", allow)
    assert cp.is_allowed("database", "x.db", "", allow)


def make_repo(tmp_path, files):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)


def test_scan_repo_reports_file_line_and_reason(tmp_path):
    make_repo(
        tmp_path,
        {
            "ok.md": b"nothing here\n",
            "notes.md": b"line one\nmail me at bob@" + b"gmail.com\n",
            "x.db": b"\x00\x01binary",
            "docs/guide/images/pic.png": b"\x89PNG\x00",
            "wide.txt": ("a\nwrite " + IP4 + "\n").encode("utf-16"),
        },
    )
    problems = cp.scan_repo(tmp_path, allowlist=[])
    assert problems == [
        "notes.md:2: [email] an email address that looks real",
        "wide.txt:2: [ip] a public IP address",
        "x.db:0: [database] a database, dump or journal file (it holds personal data)",
    ]
    assert "gmail" not in "".join(problems)  # values are never printed
    allow = [("email", "notes.md", "bob@" + "gmail.com"), ("database", "*.db", "")]
    allow += [("ip", "wide.txt", IP4)]
    assert cp.scan_repo(tmp_path, allowlist=allow) == []
    # an allowlist entry excuses only its own value
    wrong = [("email", "notes.md", "other@" + "gmail.com")]
    assert any("notes.md" in p for p in cp.scan_repo(tmp_path, allowlist=wrong))


def test_oversize_file_is_flagged(tmp_path, monkeypatch):
    make_repo(tmp_path, {"big.txt": b"x" * 50})
    monkeypatch.setattr(cp, "MAX_BYTES", 10)
    assert cp.scan_repo(tmp_path, allowlist=[]) == [
        "big.txt:0: [too-big] a file too big to check (over 2 MB)"
    ]


def test_repo_itself_is_clean():
    assert cp.scan_repo() == []
