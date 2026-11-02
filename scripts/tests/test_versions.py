"""Every copy of the version agrees with server/app/__init__.py, the one place it is set
(docs/dev/release.md), and the .exe version info is made from it."""

import json
import sys
import tomllib
from pathlib import Path

import pytest

import _common

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
import _version  # noqa: E402
import build_desktop  # noqa: E402

VERSION = _version.version()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_version_is_three_numbers():
    assert len(VERSION.split(".")) == 3 and all(part.isdigit() for part in VERSION.split("."))


def test_every_copy_of_the_version_agrees():
    desktop = tomllib.loads((_common.DESKTOP_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    mobile_lock = read_json(_common.MOBILE_DIR / "package-lock.json")
    copies = {
        "desktop/pyproject.toml": desktop["project"]["version"],
        "mobile/app.json": read_json(_common.MOBILE_DIR / "app.json")["expo"]["version"],
        "mobile/package.json": read_json(_common.MOBILE_DIR / "package.json")["version"],
        "mobile/package-lock.json": mobile_lock["version"],
        "mobile/package-lock.json (packages)": mobile_lock["packages"][""]["version"],
    }
    wrong = {where: found for where, found in copies.items() if found != VERSION}
    assert not wrong, f"Not {VERSION} as in server/app/__init__.py: {wrong} (docs/dev/release.md)"


@pytest.mark.parametrize("exe_name, description", build_desktop.EXES.values())
def test_the_exe_version_info_comes_from_the_version(exe_name, description):
    text = _version.version_info(exe_name, description)
    four = f"{VERSION}.0"
    numbers = repr(tuple(int(n) for n in four.split(".")))
    assert text.count(numbers) == 2  # filevers and prodvers
    for name, value in {
        "FileVersion": four,
        "ProductVersion": four,
        "CompanyName": "Budget Buddy",
        "ProductName": "Budget Buddy",
        "FileDescription": description,
        "OriginalFilename": f"{exe_name}.exe",
        "LegalCopyright": _version.copyright_line(),
    }.items():
        assert f"StringStruct({name!r}, {value!r})" in text
    assert _version.copyright_line().startswith("Copyright (c) 20")


def test_pyinstaller_reads_the_version_info(tmp_path):
    versioninfo = pytest.importorskip("PyInstaller.utils.win32.versioninfo")
    path = tmp_path / "version.txt"
    path.write_text(_version.version_info("Budget Buddy", "Budget Buddy"), encoding="utf-8")
    info = versioninfo.load_version_info_from_text_file(str(path))
    major, minor, patch = map(int, VERSION.split("."))
    expected = (major << 16 | minor, patch << 16)
    assert (info.ffi.fileVersionMS, info.ffi.fileVersionLS) == expected
    assert (info.ffi.productVersionMS, info.ffi.productVersionLS) == expected


def test_the_build_writes_a_version_file_for_each_recipe(monkeypatch, tmp_path):
    monkeypatch.setattr(build_desktop, "WORK", tmp_path)
    build_desktop.write_version_info()
    for recipe, (exe_name, _) in build_desktop.EXES.items():
        assert f"{exe_name}.exe" in (tmp_path / f"version-{recipe}.txt").read_text("utf-8")
        assert f'"version-{recipe}.txt"' in (_common.PACKAGING_DIR / f"{recipe}.spec").read_text()
