# Making a release

A release is one Windows download, `Budget-Buddy-<version>-Windows.zip`, plus its `.sha256`. Phones use the
dashboard in their web browser for now (Devices, Other devices; [ADR-0009](../adr/0009-other-computers.md)); the
Expo phone app isn't published to app stores yet.

## What's in the zip

| File | What it is |
| --- | --- |
| `Budget Buddy\Budget Buddy.exe` | The desktop app (window and tray), with `home-base\` (the packaged Home Base and dashboard) and `version.txt` |
| `Install Budget Buddy.bat`, `install.ps1` | Installs for the current user (no admin): `%LOCALAPPDATA%\Programs\Budget Buddy`, Start menu and desktop shortcuts, and an entry in Windows Settings, Apps |
| `Uninstall Budget Buddy.bat` | Removes the app, its shortcuts, the Apps entry and Start with Windows. Never the data folder |
| `READ ME FIRST.txt` | Plain-English install, first steps, phone, update and remove |

The sources are in `packaging/windows/`, with both PyInstaller recipes; `scripts/release/install_desktop.py` uses the same `install.ps1` for a build
from source.

## The version

The version (`MAJOR.MINOR.PATCH`, now 0.1.0) is set in one place: `__version__` in `server/app/__init__.py`. Made
from it at build time: the zip name, the installer's `version.txt`, and the version info in both `.exe` files
(Properties, Details: file and product version `0.1.0.0`, company and product "Budget Buddy", and the copyright line
from `LICENSE`), which `build_desktop.py` writes with `scripts/release/_version.py` for the `version=` in each
PyInstaller recipe. The release workflow checks the tag against it.

Some files need their own copy, and `scripts/tests/test_versions.py` fails if any of them differs:

- `desktop/pyproject.toml` (`version`); setuptools can't read the server's file. After changing it, run
  `scripts/dev/lock_dependencies.py`: the lock files record the file's fingerprint.
- `mobile/app.json` (`expo.version`, which the app sends to the Home Base as its version through
  `mobile/src/lib/appVersion.ts`), `mobile/package.json` and both `version` lines at the top of
  `mobile/package-lock.json`.

To bump it: change `server/app/__init__.py` and the copies above, run `scripts/dev/lock_dependencies.py`, then
`server/.venv/Scripts/pytest scripts/tests`.

## Checklist

1. On `main`, with every part's checks green ([testing.md](testing.md)).
2. Set the version ([The version](#the-version) lists every file that holds it). Move the `## Unreleased` lines in
   `CHANGELOG.md` under `## <version> - <date>`.
3. Build and try it locally: `py scripts/release/make_release.py`, unzip
   `dist\Budget-Buddy-<version>-Windows.zip` somewhere new, run **Install Budget Buddy**, open it from the Start
   menu, check Home's Get started list, then uninstall from Windows Settings, Apps.
4. Commit, tag `v<version>` and push the tag (only when the owner says so). `.github/workflows/release.yml`
   checks the tag matches the version, builds the zip on Windows and attaches it to a **draft** GitHub Release.
5. The owner reads the draft, pastes the CHANGELOG section into its notes and publishes it.

## Known limits

- **Not code-signed.** Windows SmartScreen shows "Windows protected your PC" the first time; the read-me explains
  **More info**, **Run anyway**. Signing needs a certificate and is a follow-up.
- **Windows only.** macOS and Linux run from source ([README](../../README.md#quick-start)).
- **Phones use the browser over plain HTTP** on the home network (see ADR-0009's consequences); HTTPS with a
  self-signed certificate is a noted follow-up.
