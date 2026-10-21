# PyInstaller recipe for the packaged Home Base, "Budget Buddy Home Base.exe": the server with the
# dashboard files bundled in (ADR-0005 asks the installer to ship them beside it). The desktop app starts
# it (ADR-0008). Built by scripts/release/build_desktop.py. No console window: output goes nowhere unless
# the program that starts it collects it.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

REPO = Path(SPECPATH).parents[1]  # this file is in packaging\windows\
SERVER = REPO / "server"
DASHBOARD = REPO / "dashboard"
# PyInstaller adds the recipe name to workpath; the build script draws the icon one level up.
ICON = Path(workpath).parent / "budget-buddy.ico"

datas = [
    # Only what the server serves: index.html, top-level CSS, js/**/*.js (app/dashboard_files.py).
    (str(DASHBOARD / "index.html"), "dashboard"),
    *[(str(css), "dashboard") for css in DASHBOARD.glob("*.css")],
    *[
        (str(js), str(Path("dashboard") / js.parent.relative_to(DASHBOARD)))
        for js in DASHBOARD.glob("js/**/*.js")
    ],
    # Alembic reads the migration scripts from disk; the tax data is read as package files.
    (str(SERVER / "app" / "migrations"), "app/migrations"),
    *[(str(f), "app/tax_data") for f in (SERVER / "app" / "tax_data").glob("*.json")],
]

a = Analysis(
    [str(SERVER / "app" / "__main__.py")],
    pathex=[str(SERVER)],
    datas=datas,
    # Loaded by name at run time: our routers and uvicorn's loops, protocols and lifespan.
    hiddenimports=[*collect_submodules("app"), *collect_submodules("uvicorn")],
    # Never used by the server. Alembic's Mako templates can colour error pages with Pygments, whose
    # image formatter pulls in Pillow (about 16 MB); without them Mako falls back to plain text.
    # setuptools and numpy are found through other packages' optional imports.
    excludes=[
        "pytest", "ruff", "tkinter", "setuptools", "numpy",
        "PIL", "pygments", "mako.ext.pygmentplugin",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Budget Buddy Home Base",
    console=False,
    icon=str(ICON),
)
coll = COLLECT(exe, a.binaries, a.datas, name="home-base")
