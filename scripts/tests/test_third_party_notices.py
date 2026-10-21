"""THIRD-PARTY-NOTICES.txt is built from the packaged libraries' own licence files (roadmap 25b),
and the build stops, naming the package, if one has none."""

import json
import sys
from importlib import metadata
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
import third_party_notices as tpn  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LOCKS = [REPO / part / "requirements-package.txt" for part in ("server", "desktop")]


def fake_dist(site: Path, name: str, files: dict[str, str], extra_metadata: str = "") -> None:
    info = site / f"{name}-1.0.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.4\nName: {name}\nVersion: 1.0\n{extra_metadata}", "utf-8"
    )
    record = [f"{name}-1.0.dist-info/METADATA,,"]
    for file, text in files.items():
        target = info / file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, "utf-8")
        record.append(f"{name}-1.0.dist-info/{file},,")
    (info / "RECORD").write_text("\n".join(record), "utf-8")


@pytest.fixture
def site(tmp_path, monkeypatch):
    folder = tmp_path / "site"
    folder.mkdir()
    monkeypatch.syspath_prepend(str(folder))
    return folder


def lock_of(tmp_path: Path, *lines: str) -> Path:
    lock = tmp_path / "requirements-package.txt"
    lock.write_text("\n".join(lines) + "\n", "utf-8")
    return lock


def result(packages: list[dict]) -> dict:
    return {"packages": packages, "python": "PSF text", "python_version": "3.14.0"}


def test_packages_for_other_systems_are_left_out(tmp_path):
    lock = lock_of(
        tmp_path,
        "# comment",
        "alpha==1.0 \\",
        "    --hash=sha256:aa",
        "winonly==2.0 ; sys_platform == 'win32' \\",
        "    --hash=sha256:bb",
        "macos==3.0 ; sys_platform == 'darwin' \\",
        "    --hash=sha256:cc",
        "Some_Pkg.x==4.0 ; platform_python_implementation != 'PyPy' \\",
    )
    assert tpn.locked_packages(lock) == {"alpha": "1.0", "winonly": "2.0", "some-pkg-x": "4.0"}


def test_licence_files_are_read_from_the_dist_info_folder(site, tmp_path):
    fake_dist(
        site,
        "alpha",
        {"licenses/LICENSE": "ALPHA TEXT", "licenses/sub/LICENSE.dep": "DEP TEXT"},
        "License-Expression: MIT\nLicense-File: LICENSE\n",
    )
    fake_dist(site, "beta", {"COPYING": "BETA TEXT"}, "License: BSD-3-Clause\n")
    found = tpn.collect(lock_of(tmp_path, "alpha==1.0 \\", "beta==1.0 \\"))["packages"]
    by_name = {p["name"]: p for p in found}
    assert by_name["alpha"]["texts"] == {"LICENSE": "ALPHA TEXT", "sub/LICENSE.dep": "DEP TEXT"}
    assert by_name["alpha"]["licence"] == "MIT"
    assert by_name["beta"]["texts"] == {"COPYING": "BETA TEXT"}
    assert by_name["beta"]["licence"] == "BSD-3-Clause"


def test_a_package_without_a_licence_text_stops_the_build_and_is_named():
    package = {"name": "mystery-pkg", "version": "1.0", "licence": "MIT", "url": "", "texts": {}}
    with pytest.raises(ValueError, match="mystery-pkg"):
        tpn.render([result([package])], [])


def test_a_package_that_is_not_installed_is_named(site, tmp_path):
    found = tpn.collect(lock_of(tmp_path, "not-installed-anywhere==1.0 \\"))["packages"]
    with pytest.raises(ValueError, match="not-installed-anywhere"):
        tpn.render([result(found)], [])


def test_the_notices_hold_every_text_extras_and_the_python_licence():
    package = {
        "name": "alpha",
        "version": "1.0",
        "licence": "MIT",
        "url": "",
        "texts": {"LICENSE": "ALPHA TEXT"},
    }
    lib = {
        "name": "libfoo",
        "licence": "ISC",
        "source": "inside alpha",
        "note": "N",
        "text_from": {"package": "alpha", "file": "LICENSE"},
    }
    text = tpn.render([result([package])], [lib])
    for wanted in ("alpha 1.0", "ALPHA TEXT", "libfoo", "inside alpha", "PSF text", "Budget Buddy"):
        assert wanted in text
    broken = {**lib, "text_from": {"package": "alpha", "file": "NOPE"}}
    with pytest.raises(ValueError, match="libfoo"):
        tpn.render([result([package])], [broken])


def test_every_locked_package_has_a_licence_text_or_a_checked_in_one():
    """For what is installed here. The build repeats this on the real build venvs (build_desktop.py
    stops on the first package without a text), where everything in the lock files is installed."""
    seen, checked = set(), 0
    for lock in LOCKS:
        for name in tpn.locked_packages(lock):
            seen.add(name)
            try:
                dist = metadata.distribution(name)
            except metadata.PackageNotFoundError:
                continue  # not installed in this environment; the build checks it
            checked += 1
            has_text = (
                bool(tpn.dist_texts(dist)) or (tpn.PACKAGING / "licences" / f"{name}.txt").exists()
            )
            assert has_text, f"{name} has no licence text"
    assert checked >= 5 and len(seen) >= 40


def test_checked_in_licence_files_and_extras_point_at_real_packages():
    locked = {name for lock in LOCKS for name in tpn.locked_packages(lock)}
    extras = json.loads((tpn.PACKAGING / "extra-notices.json").read_text("utf-8"))
    used = {Path(extra["text_file"]).name for extra in extras if "text_file" in extra}
    for file in (tpn.PACKAGING / "licences").glob("*.txt"):
        assert file.name in used or file.stem in locked, f"{file.name} isn't used"
    for extra in extras:
        assert {"id", "name", "licence", "source", "note"} <= extra.keys()
        if "text_from" in extra:
            assert tpn.norm(extra["text_from"]["package"]) in locked, extra["name"]
        if "text_file" in extra:
            assert (tpn.PACKAGING / extra["text_file"]).is_file()
    assert {id_ for id_ in tpn.BUNDLED.values()} <= {extra["id"] for extra in extras}


def test_bundled_code_without_a_notice_stops_the_build(tmp_path):
    (tmp_path / "webview" / "lib").mkdir(parents=True)
    (tmp_path / "webview" / "lib" / "Microsoft.Web.WebView2.Core.dll").write_bytes(b"x")
    assert "WebView2" in tpn.uncovered(tmp_path, [{"id": "libsodium"}])[0]
    assert tpn.uncovered(tmp_path, [{"id": "webview2"}]) == []


def test_a_lock_line_that_cannot_be_read_is_an_error(tmp_path):
    lock = lock_of(
        tmp_path, "alpha==1.0 \\", "    --hash=sha256:aa", "    # via x", "alpha @ https://x"
    )
    with pytest.raises(ValueError, match="alpha @"):
        tpn.locked_packages(lock)


def test_the_packages_the_old_list_missed_are_all_locked():
    locked = {name for lock in LOCKS for name in tpn.locked_packages(lock)}
    wanted = """bottle proxy-tools mako markupsafe jaraco-classes jaraco-context jaraco-functools
        more-itertools click h11 anyio idna cffi pycparser pywin32-ctypes python-dotenv
        opentelemetry-api cryptography pynacl pillow pystray pyinstaller""".split()
    assert [name for name in wanted if name not in locked] == []
