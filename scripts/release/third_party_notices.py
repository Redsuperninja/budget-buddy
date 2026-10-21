"""Build THIRD-PARTY-NOTICES.txt for the Windows download (roadmap 25b) from the licence files that
the packaged libraries ship with, so the list can't fall behind the lock files.

The list of packages comes from each part's requirements-package.txt (what the build venvs
install; packages for other systems, like pyobjc on macOS, are left out). For each one the
installed copy's own metadata and licence files are read (importlib.metadata: the dist-info
"licenses" folder, License-File, License-Expression). Three things are added by hand because no
package carries them as a licence file of its own:
  - packaging/windows/licences/<name>.txt: a package whose wheel has no licence file (says why),
  - packaging/windows/extra-notices.json: C libraries inside wheels (OpenSSL, libsodium, Pillow's
    image libraries), with the file in the wheel their text comes from,
  - the Python runtime's LICENSE.txt, read from the Python the venv was made from.
A package with no licence text anywhere stops the build and is named.

build_desktop.py calls write(); "third_party_notices.py --collect <lock>" is what runs inside each
build venv (stdlib and packaging only) and prints JSON.
"""

import json
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGING = HERE.parents[1] / "packaging" / "windows"
LICENCE_NAME = re.compile(r"licen[cs]e|copying|notice", re.IGNORECASE)
RULE = "=" * 78
WINDOWS = {
    "sys_platform": "win32",
    "platform_system": "Windows",
    "os_name": "nt",
    "platform_machine": "AMD64",
    "implementation_name": "cpython",
    "platform_python_implementation": "CPython",
}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def locked_packages(lock: Path) -> dict[str, str]:
    """{normalised name: version} of the lock's packages that are installed on Windows."""
    from packaging.markers import Marker

    found = {}
    for line in lock.read_text("utf-8").splitlines():
        match = re.match(
            r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)\s*(?:;\s*([^\\]+?))?\s*\\?$", line
        )
        if not match:
            if line.strip() and not line.lstrip().startswith(("#", "--hash=")):
                raise ValueError(f"{lock.name}: can't read the line {line!r}")
            continue
        if not match[3] or Marker(match[3]).evaluate(WINDOWS):
            found[norm(match[1])] = match[2]
    return found


def dist_texts(dist: metadata.Distribution) -> dict[str, str]:
    """{path inside dist-info, without its "licenses/" folder: text} of the licence files."""
    declared = set(dist.metadata.get_all("License-File") or [])
    texts = {}
    for file in dist.files or []:
        parts = file.parts
        info = next((n for n, part in enumerate(parts[:-1]) if part.endswith(".dist-info")), None)
        if info is None or "sboms" in parts:
            continue
        inside = parts[info + 1 :]
        key = "/".join(inside[1:] if inside[0] == "licenses" and len(inside) > 1 else inside)
        if key in declared or "licenses" in inside or LICENCE_NAME.search(file.name):
            texts[key] = Path(dist.locate_file(file)).read_text("utf-8", errors="replace")
    return texts


def licence_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    text = meta.get("License-Expression") or meta.get("License") or ""
    if not text or "\n" in text or len(text) > 60:  # a whole licence text, not a name
        names = [
            c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if "License ::" in c
        ]
        text = ", ".join(names) or (text.splitlines()[0][:60] if text else "")
    return text


def collect(lock: Path) -> dict:
    """Run inside a build venv: what its packages and its Python say about their licences."""
    packages = []
    for name, version in sorted(locked_packages(lock).items()):
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            packages.append({"name": name, "version": version, "missing": True})
            continue
        packages.append(
            {
                "name": dist.metadata["Name"],
                "version": dist.version,
                "licence": licence_of(dist),
                "url": dist.metadata.get("Home-page") or "",
                "texts": dist_texts(dist),
            }
        )
    python = Path(sys.base_prefix) / "LICENSE.txt"
    runtime = python.read_text("utf-8", errors="replace") if python.exists() else ""
    return {"packages": packages, "python": runtime, "python_version": sys.version.split()[0]}


def add_fallback(package: dict) -> None:
    """Use the checked-in text for a package whose wheel carries no licence file."""
    fallback = PACKAGING / "licences" / f"{norm(package['name'])}.txt"
    if fallback.exists():
        package["texts"] = {fallback.name: fallback.read_text("utf-8")}


def render(results: list[dict], extras: list[dict]) -> str:
    """The whole notices file. Raises ValueError naming every package without a licence text."""
    packages = {}
    for result in results:
        for package in result["packages"]:
            if not package.get("missing") and not package["texts"]:
                add_fallback(package)
            packages.setdefault(norm(package["name"]), package)
    problems = [
        f"{key}: not installed in the build venv" if p.get("missing") else f"{key}: no licence text"
        for key, p in sorted(packages.items()) if p.get("missing") or not p["texts"]
    ]  # fmt: skip
    runtime = next((r["python"] for r in results if r["python"]), "")
    if not runtime:
        problems.append("python: no LICENSE.txt next to the Python that made the build venv")
    extra_texts = [(extra, extra_text(extra, packages)) for extra in extras]
    problems += [f"{e['name']}: {text}" for e, text in extra_texts if text.startswith("!")]
    if problems:
        raise ValueError("Licence texts missing:\n  " + "\n  ".join(problems))

    out = [
        (PACKAGING / "notices-header.txt").read_text("utf-8").rstrip(),
        "",
        "Packages in this download:",
    ]
    for package in sorted(packages.values(), key=lambda p: p["name"].lower()):
        out.append(
            f"  {package['name']} {package['version']}  -  {package['licence'] or 'see text below'}"
        )
    for package in sorted(packages.values(), key=lambda p: p["name"].lower()):
        out += ["", RULE, f"{package['name']} {package['version']}  ({package['licence']})"]
        out += [package["url"]] if package["url"] else []
        for file, text in package["texts"].items():
            out += [RULE, f"[{file}]", "", text.strip()]
    for extra, text in extra_texts:
        out += ["", RULE, f"{extra['name']}  ({extra['licence']})", f"Source: {extra['source']}"]
        out += [extra["note"], "", text.strip()] if text else [extra["note"]]
    out += [
        "",
        RULE,
        f"Python {results[0]['python_version']} runtime (PSF-2.0 licence)",
        RULE,
        "",
        runtime.strip(),
    ]
    return "\n".join(out) + "\n"


def extra_text(extra: dict, packages: dict) -> str:
    """The licence text an extra notice points at, or '!reason' if it can't be found."""
    if "text_file" in extra:
        return (PACKAGING / extra["text_file"]).read_text("utf-8")
    source = extra.get("text_from")
    if not source:
        return ""
    package = packages.get(norm(source["package"]))
    text = package and package["texts"].get(source["file"])
    return text or f"!{source['file']} not found in {source['package']}"


# Files in the built app that carry code from outside the Python packages, and the "id" of the
# extra notice that covers them. A build that has one without the notice stops.
BUNDLED = {
    "*WebView2*.dll": "webview2",
    "libcrypto*.dll": "python-runtime",
    "sqlite3.dll": "python-runtime",
    "_sodium*.pyd": "libsodium",
}


def uncovered(app_dir: Path, extras: list[dict]) -> list[str]:
    """What is bundled in ``app_dir`` that no extra notice (by "id") covers."""
    have = {extra.get("id") for extra in extras}
    return [
        f"{pattern} is in the app but there is no extra notice with id '{id_}'"
        for pattern, id_ in BUNDLED.items()
        if id_ not in have and next(app_dir.rglob(pattern), None)
    ]


def write(out: Path, builds: list[tuple[Path, Path]]) -> None:
    """Write ``out`` (in the app folder) from [(python of a build venv, its lock), ...]."""
    results = []
    for python, lock in builds:
        run = subprocess.run(
            [str(python), "-I", str(Path(__file__).resolve()), "--collect", str(lock)],
            capture_output=True, text=True, encoding="utf-8",
        )  # fmt: skip
        if run.returncode:
            raise RuntimeError(f"Reading the licences from {python} failed:\n{run.stderr}")
        results.append(json.loads(run.stdout))
    extras = json.loads((PACKAGING / "extra-notices.json").read_text("utf-8"))
    if missing := uncovered(out.parent, extras):
        raise ValueError("Bundled code without a notice:\n  " + "\n  ".join(missing))
    out.write_text(render(results, extras), encoding="utf-8")


def main(args: list[str]) -> int:
    if len(args) != 2 or args[0] != "--collect":
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(Path(args[1])), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
