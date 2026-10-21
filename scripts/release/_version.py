"""The release version and the Windows version info made from it (docs/dev/release.md).

The version lives only in server/app/__init__.py. The zip name, the installer's version.txt and the
version info in both .exe files are made from it here; the other copies (desktop/pyproject.toml,
mobile/app.json, mobile/package.json) are checked against it by scripts/tests/test_versions.py.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/, for _common

from _common import REPO, SERVER_DIR, stop  # noqa: E402

VERSION_FILE = SERVER_DIR / "app" / "__init__.py"
COMPANY = PRODUCT = "Budget Buddy"


def version() -> str:
    """The release version, like "0.1.0"."""
    text = VERSION_FILE.read_text("utf-8")
    found = re.search(r'^__version__ = "(\d+)\.(\d+)\.(\d+)"$', text, re.M)
    if not found:
        stop(f'No __version__ = "X.Y.Z" in {VERSION_FILE.relative_to(REPO)}.')
    return ".".join(found.groups())


def copyright_line() -> str:
    """The "Copyright (c) <year> <who>" line of LICENSE."""
    for line in (REPO / "LICENSE").read_text("utf-8").splitlines():
        if line.startswith("Copyright"):
            return line.strip()
    stop("No Copyright line in LICENSE.")


def version_info(exe_name: str, description: str) -> str:
    """A PyInstaller version file (the ``version=`` of EXE in a .spec) for ``exe_name``.exe:
    what Windows shows in the file's Properties, Details."""
    numbers = (*map(int, version().split(".")), 0)
    strings = {
        "CompanyName": COMPANY,
        "FileDescription": description,
        "FileVersion": ".".join(map(str, numbers)),
        "InternalName": exe_name,
        "LegalCopyright": copyright_line(),
        "OriginalFilename": f"{exe_name}.exe",
        "ProductName": PRODUCT,
        "ProductVersion": ".".join(map(str, numbers)),
    }
    table = ",\n".join(f"          StringStruct({k!r}, {v!r})" for k, v in strings.items())
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers!r},
    prodvers={numbers!r},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
{table},
      ]),
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""
