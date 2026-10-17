"""The lock files are up to date: each was made from its part's current pyproject.toml."""

import sys
from pathlib import Path

import pytest

import _common

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dev"))
from lock_dependencies import lock_header  # noqa: E402

PARTS = [_common.SERVER_DIR, _common.DESKTOP_DIR]


@pytest.mark.parametrize("part_dir", PARTS, ids=lambda p: p.name)
@pytest.mark.parametrize("lock", _common.LOCKS)
def test_lock_file_matches_pyproject(part_dir, lock):
    first_line = (part_dir / lock).read_text(encoding="utf-8").splitlines(keepends=True)[0]
    assert first_line == lock_header(part_dir), (
        f"{part_dir.name}/{lock} is older than pyproject.toml: run scripts/dev/lock_dependencies.py"
    )


@pytest.mark.parametrize("part_dir", PARTS, ids=lambda p: p.name)
def test_every_package_has_an_exact_version_and_a_hash(part_dir):
    for lock in _common.LOCKS:
        text = (part_dir / lock).read_text(encoding="utf-8")
        packages = [line for line in text.splitlines() if line[:1].isalnum()]
        assert packages and all("==" in line for line in packages)
        assert text.count("==") <= text.count("--hash=sha256:")
