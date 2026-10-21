"""Write the lock files: the exact version and hashes of every package the Home Base and the desktop
app install, on Windows, macOS and Linux alike (ADR-0013). Run it after changing a pyproject.toml,
and with --upgrade to move every package to its newest allowed version. Needs uv
(https://docs.astral.sh/uv/; `pip install uv` works); installing only needs pip.

    python3 scripts/dev/lock_dependencies.py [--upgrade]      (on Windows, type py)

Each part gets requirements-build.txt (setuptools, installed first so a package without a ready-made
wheel is built with a checked copy), requirements.txt (what Start Budget Buddy installs) and
requirements-dev.txt (plus every extra: tests, linter, packaging) and requirements-package.txt
(plus only packaging: what the release build installs), all with the same versions.
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))  # for _common

from _common import DESKTOP_DIR, LOCKS, SERVER_DIR, say, stop  # noqa: E402

HEADER = "# Made by scripts/dev/lock_dependencies.py from pyproject.toml sha256 "
PYTHON = "3.12"  # the oldest Python the parts support; the files work for newer ones too
# Packages that are only ever installed from a ready-made wheel, never built from source: a missing
# wheel must fail the install, not compile against whatever OpenSSL the computer has (ADR-0014).
# The script writes a matching `--only-binary` line into each lock file that has the package.
BINARY_ONLY = ("sqlcipher3",)


def lock_header(part_dir: Path) -> str:
    digest = hashlib.sha256((part_dir / "pyproject.toml").read_bytes()).hexdigest()
    return f"{HEADER}{digest}; don't edit by hand.\n"


def packaging_extras(part_dir: Path) -> list[str]:
    """The extras that build the app (PyInstaller): every one but "dev" (tests and linter)."""
    pyproject = tomllib.loads((part_dir / "pyproject.toml").read_text(encoding="utf-8"))
    return [name for name in pyproject["project"]["optional-dependencies"] if name != "dev"]


def compile_lock(uv: str, part_dir: Path, out: str, extra: list[str], upgrade: bool) -> None:
    """One lock file from the part's build tool (setuptools, read from stdin) and ``extra``."""
    pyproject = tomllib.loads((part_dir / "pyproject.toml").read_text(encoding="utf-8"))
    build_tools = "\n".join(pyproject["build-system"]["requires"])
    command = [uv, "pip", "compile", "-", "--universal", "--python-version", PYTHON,
               "--generate-hashes", "--no-header", "--annotation-style", "line", "--quiet",
               "-o", out, *extra, *(["--upgrade"] if upgrade else []),
               *[f"--only-binary={name}" for name in BINARY_ONLY]]  # fmt: skip
    done = subprocess.run(command, cwd=part_dir, input=build_tools, text=True)
    if done.returncode:
        stop(f"Locking {part_dir.name}/{out} failed; the messages above say why.")
    path = part_dir / out
    body = "".join(line for line in path.read_text(encoding="utf-8").splitlines(keepends=True)
                   if not line.startswith((HEADER, "--only-binary")))  # fmt: skip
    # One line per package that is in this file. pip obeys it, so every installer fails rather
    # than building the package from source.
    only_binary = "".join(f"--only-binary {name}\n" for name in BINARY_ONLY
                          if f"\n{name}==" in "\n" + body)  # fmt: skip
    path.write_text(lock_header(part_dir) + only_binary + body, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the server's and desktop app's lock files.")
    parser.add_argument("--upgrade", action="store_true", help="move to newer allowed versions")
    upgrade = parser.parse_args().upgrade
    uv = shutil.which("uv")
    if not uv:
        stop("Needs uv: install it with `pip install uv` (https://docs.astral.sh/uv/).")
    build, runtime, dev, package = LOCKS
    for part_dir in SERVER_DIR, DESKTOP_DIR:
        compile_lock(uv, part_dir, runtime, ["pyproject.toml"], upgrade)
        # The same versions as the runtime file for every package they share.
        compile_lock(uv, part_dir, dev, ["pyproject.toml", "--all-extras", "-c", runtime], upgrade)
        # What the release build installs: the app and PyInstaller, at the dev file's versions.
        extras = [f"--extra={name}" for name in packaging_extras(part_dir)]
        compile_lock(uv, part_dir, package, ["pyproject.toml", *extras, "-c", dev], upgrade)
        compile_lock(uv, part_dir, build, ["-c", runtime], upgrade)
        say(f"Wrote {part_dir.name}/{build}, {runtime}, {dev} and {package}.", "green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
