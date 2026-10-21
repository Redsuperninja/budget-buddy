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


def pins(lock_path: Path) -> dict[str, tuple[str, frozenset[str]]]:
    """{package: (version, hashes)} from a lock file."""
    found, name = {}, None
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        if line[:1].isalnum():
            name, _, rest = line.partition("==")
            found[name] = (rest.split()[0], frozenset())
        elif name and line.strip().startswith("--hash="):
            version, hashes = found[name]
            found[name] = (version, hashes | {line.strip().split("=", 1)[1].rstrip(" \\")})
    return found


@pytest.mark.parametrize("part_dir", PARTS, ids=lambda p: p.name)
def test_the_release_build_uses_the_tested_versions(part_dir):
    """Dependabot updates each lock file on its own: the release build's file must still match
    the dev file (what CI tests) exactly, version and hashes."""
    package, dev = pins(part_dir / _common.PACKAGE_LOCK), pins(part_dir / _common.DEV_LOCK)
    assert package
    for name, pin in package.items():
        assert dev.get(name) == pin, (
            f"{part_dir.name}/{_common.PACKAGE_LOCK} has {name} {pin[0]}, not as in "
            f"{_common.DEV_LOCK}: run scripts/dev/lock_dependencies.py"
        )
