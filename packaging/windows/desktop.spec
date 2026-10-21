# PyInstaller recipe for "Budget Buddy.exe", the desktop app (roadmap 22, ADR-0008). Built by
# scripts/release/build_desktop.py, which puts the packaged Home Base (home-base.spec, beside this file) in its
# home-base folder. One folder, not one file: it starts faster.
from pathlib import Path

DESKTOP = Path(SPECPATH).parents[1] / "desktop"  # this file is in packaging\windows\
# PyInstaller adds the recipe name to workpath; the build script draws the icon one level up.
ICON = Path(workpath).parent / "budget-buddy.ico"

a = Analysis(
    [str(DESKTOP / "budget_buddy_desktop" / "__main__.py")],
    pathex=[str(DESKTOP)],
    hiddenimports=["pystray._win32"],  # pystray picks its Windows backend by name
    # Never used by the app. Pillow only draws the icon: no AVIF, WebP or colour profiles, and no Tk.
    # Keep PIL._imagingft (the icon's letter uses ImageFont) and ssl (pywebview imports it on start,
    # though the app only talks to 127.0.0.1 over plain http).
    excludes=[
        "pytest", "ruff", "tkinter", "setuptools", "pydoc_data",
        "PIL._avif", "PIL._webp", "PIL._imagingcms", "PIL.ImageTk",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Budget Buddy",
    console=False,
    icon=str(ICON),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Budget Buddy")
