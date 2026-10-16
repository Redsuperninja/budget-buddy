"""Make the Windows download for a release: dist/Budget-Buddy-<version>-Windows.zip and its .sha256.
The zip holds the built app (build_desktop.py), the installer and a plain-English READ ME FIRST.txt,
so nobody needs Python or this repository to use it. The version comes from server/app/__init__.py.
(docs/dev/release.md has the full checklist; .github/workflows/release.yml runs this for a v* tag.)

    py scripts/release/make_release.py
"""

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/, for _common

from _common import PACKAGING_DIR, REPO, SERVER_DIR, require_windows, say, stop  # noqa: E402

INSTALLER = (
    "install.ps1",
    "Install Budget Buddy.bat",
    "Uninstall Budget Buddy.bat",
    "READ ME FIRST.txt",
)


def version() -> str:
    found = re.search(
        r'__version__ = "([^"]+)"', (SERVER_DIR / "app" / "__init__.py").read_text("utf-8")
    )
    if not found:
        stop("No __version__ in server/app/__init__.py.")
    return found[1]


def zip_folder(folder: Path, zip_path: Path) -> None:
    """Zip ``folder`` (as the top folder in the zip), with "/" in names so every unzip tool,
    macOS's too, reads them as folders."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(p for p in folder.rglob("*") if p.is_file()):
            archive.write(file, file.relative_to(folder.parent).as_posix())


def main() -> int:
    argparse.ArgumentParser(description="Make the Windows download for a release.").parse_args()
    require_windows("The Windows download")
    number = version()
    name = f"Budget-Buddy-{number}-Windows"
    stage, dist = REPO / "build" / "release" / name, REPO / "dist"
    zip_path = dist / f"{name}.zip"
    shutil.rmtree(stage, ignore_errors=True)
    if stage.exists():  # an old file left behind would end up in the zip
        stop(f"Couldn't clear {stage}. Close anything using it, then try again.")
    stage.mkdir(parents=True)
    dist.mkdir(exist_ok=True)

    build = [sys.executable, Path(__file__).with_name("build_desktop.py"), "--into", stage]
    if subprocess.run([str(part) for part in build]).returncode:
        return 1
    (stage / "Budget Buddy" / "version.txt").write_text(number + "\n", encoding="ascii")
    for file in INSTALLER:
        shutil.copy(PACKAGING_DIR / file, stage)

    zip_path.unlink(missing_ok=True)
    zip_folder(stage, zip_path)
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    checksum = zip_path.with_name(zip_path.name + ".sha256")
    checksum.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii")

    say()
    say(f"Release ready: {zip_path}", "green")
    say(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
