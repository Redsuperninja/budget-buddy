# packaging/

Everything that turns the source into the Windows download, in one place. The installer stays PowerShell: it
runs where Python isn't installed ([ADR-0011](../docs/adr/0011-cross-platform-scripts.md)). Built by
`scripts/release/build_desktop.py` (the app) and `scripts/release/make_release.py` (the zip); see
[release.md](../docs/dev/release.md) and [desktop.md](../docs/dev/architecture/desktop.md).

| `windows/` file | What it is |
| --- | --- |
| `desktop.spec` | PyInstaller recipe for `Budget Buddy.exe`, the window and tray icon (`desktop/`) |
| `home-base.spec` | PyInstaller recipe for the packaged Home Base (`server/`), with the dashboard files it serves bundled in |
| `install.ps1`, `Install Budget Buddy.bat`, `Uninstall Budget Buddy.bat` | The installer in the download; `scripts/release/install_desktop.py` uses the same `install.ps1` for a build from source |
| `READ ME FIRST.txt` | Plain-English install, first steps, phone, update and remove, for the download |
| `THIRD-PARTY-NOTICES.txt` | Licenses of what the built app includes |

The recipes find `server/`, `dashboard/` and `desktop/` from their own place (two folders up), so move them together.
