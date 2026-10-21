"""scripts/dev/check_public.py: what it flags, what it lets through, and the allowlist."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dev"))

import check_public as cp  # noqa: E402

# Sample "real" values are built from parts so this file doesn't trip the check itself.
REAL_USER = "ali" + "ce"
WIN = "C:" + "\\Users\\"
REAL_IP = ".".join(["8", "8", "8", "8"])


def rules(text, rel="a.md"):
    return [rule for _, rule, _ in cp.scan_text(rel, text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail bob@" + "gmail.com now", ["email"]),
        ("bob@example.com, x@y.example.org, noreply@github.com", []),
        ("12345+me@users.noreply.github.com", []),
        ("see icon@2x.png", []),
        (WIN + REAL_USER + "\\Documents", ["home-path"]),
        ("/Users/" + REAL_USER + "/x and /home/" + REAL_USER, ["home-path", "home-path"]),
        (WIN + "<you>\\x, /home/YOUR_NAME/x, /Users/example/x, C:\\Users\\Public", []),
        ("import ./screens/home/home.js and a/Users/", []),
        ("host " + REAL_IP, ["ip"]),
        ("192.168.1.2 10.0.0.1 127.0.0.1 0.0.0.0 203.0.113.7 198.51.100.1 192.0.2.4", []),
        ("version 3.54.0.0 and pkg==1.2.3.4", []),
        ("999.1.1.1 and 1.2.3", []),
    ],
)
def test_scan_text(text, expected):
    assert rules(text) == expected


def test_lock_files_skip_ip_check():
    assert rules("x " + REAL_IP, "requirements.txt") == []


@pytest.mark.parametrize(
    ("rel", "expected"),
    [
        (".env", ["env-file"]),
        ("server/.env.local", ["env-file"]),
        (".env.example", []),
        ("data/budget.db", ["database"]),
        ("x/y.sqlite3", ["database"]),
        ("backups/a.bbbackup", ["backup"]),
        ("certs/server.pem", ["key-file"]),
        ("id_rsa", ["key-file"]),
        ("receipts/r1.jpg", ["image"]),
        ("mobile/assets/icon.png", []),
        ("docs/guide/images/home.png", []),
        ("dashboard/app.css", []),
    ],
)
def test_scan_name(rel, expected):
    assert [rule for rule, _ in cp.scan_name(rel)] == expected


def test_allowlist_parsing_and_matching(tmp_path):
    f = tmp_path / "allow.txt"
    f.write_text("# note\n\nip docs/*.md  # why\n", encoding="utf-8")
    allow = cp.load_allowlist(f)
    assert allow == [("ip", "docs/*.md")]
    assert cp.is_allowed("ip", "docs/a.md", allow)
    assert not cp.is_allowed("email", "docs/a.md", allow)
    assert not cp.is_allowed("ip", "src/a.md", allow)


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
            "docs/pic.png": b"\x89PNG\x00",
        },
    )
    problems = cp.scan_repo(tmp_path, allowlist=[])
    assert problems == [
        "notes.md:2: [email] an email address that looks real",
        "x.db:0: [database] a database file (it holds personal data)",
    ]
    assert cp.scan_repo(tmp_path, allowlist=[("email", "notes.md"), ("database", "*.db")]) == []


def test_repo_itself_is_clean():
    assert cp.scan_repo() == []
