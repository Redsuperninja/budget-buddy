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

The sources are in `desktop/packaging/`; `scripts/release/install-desktop.ps1` uses the same `install.ps1` for a build
from source.

## Checklist

1. On `main`, with every part's checks green ([testing.md](testing.md)).
2. Set the version in `server/app/__init__.py`, the only place it lives (the zip name and the installer's
   `version.txt` come from it). Move the `## Unreleased` lines in `CHANGELOG.md` under `## <version> - <date>`.
3. Build and try it locally: `powershell -ExecutionPolicy Bypass -File scripts\release\make-release.ps1`, unzip
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
