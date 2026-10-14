"""Every address the other parts call is a route the Home Base really has.

The dashboard, the phone app, the desktop app and the scripts reach the server only over HTTP, so a
renamed or removed route would break them without failing any of their own tests. This reads their
source (it never imports it) and checks each ``/api/...`` address, and its method where the caller
names one, against this app's route table.
"""

import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

REPO = Path(__file__).resolve().parents[2]
ENDPOINTS = REPO / "dashboard" / "js" / "api" / "endpoints.js"
METHODS = "GET|POST|PUT|PATCH|DELETE"


def normalize(path: str) -> str:
    """``/a/${id}/b?x=1`` and ``/a/{id}/b`` both become ``/a/{}/b``."""
    path = path.split("?")[0]
    return re.sub(r"\$?\{[^}]*\}", "{}", path)


def api_routes(routes) -> list[APIRoute]:
    """Every APIRoute, also inside the routers main.py includes (newer FastAPI keeps those wrapped).
    main.py includes routers without a prefix, so each route's own path is its address."""
    found = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
        elif inner := getattr(route, "original_router", None):
            found += api_routes(inner.routes)
    return found


@pytest.fixture
def routes(client) -> set[tuple[str, str]]:
    table = {
        (method, normalize(route.path))
        for route in api_routes(client.app.routes)
        for method in route.methods
    }
    assert ("GET", "/api/health") in table  # the walk above still finds the routers
    return table


def dashboard_calls() -> list[tuple[str, str, str]]:
    """(method, path, line) for each exported function in endpoints.js."""
    text = ENDPOINTS.read_text(encoding="utf-8")
    local = re.search(r'const LOCAL = "([^"]+)";', text)[1]
    helpers = dict(re.findall(r"^const (\w+) = \(\w+\) => `([^`]+)`;", text, re.M))

    def expand(template: str) -> str:
        template = template.replace("${LOCAL}", local)
        return re.sub(r"\$\{(\w+)\(\w+\)\}", lambda m: expand(helpers[m[1]]), template)

    calls = []
    # One export can run over several lines, up to its closing ";".
    for line in re.findall(r"^export const .*?;$", text, re.M | re.S):
        if found := re.search(rf'api\("({METHODS})",\s*[`"]([^`"]+)[`"]', line):
            method, path = found.groups()
        elif found := re.search(r"sendCsv\(`([^`]+)`", line):
            method, path = "POST", found[1]  # a file upload
        elif found := re.search(r"=> `([^`]+)`;", line):
            method, path = "GET", found[1]  # a link the browser opens or downloads
        else:
            pytest.fail(f"endpoints.js: can't tell which route this calls: {line}")
        calls.append((method, normalize(expand(path)), line))
    return calls


def source_files() -> list[Path]:
    """The scripts, the desktop app and the phone app, without their tests or build output."""
    found = [
        *REPO.joinpath("scripts").rglob("*.py"),
        *REPO.joinpath("desktop", "budget_buddy_desktop").rglob("*.py"),
        *REPO.joinpath("mobile", "src").rglob("*.ts"),
        *REPO.joinpath("mobile", "src").rglob("*.tsx"),
    ]
    return [f for f in found if "__tests__" not in f.parts and "__pycache__" not in f.parts]


def test_the_dashboard_calls_only_routes_that_exist(routes):
    calls = dashboard_calls()
    assert len(calls) > 50  # the reader found them; a format change can't make this pass empty
    missing = [line for method, path, line in calls if (method, path) not in routes]
    assert not missing, "dashboard/js/api/endpoints.js calls routes the server doesn't have:\n" + (
        "\n".join(missing)
    )


def test_scripts_desktop_and_phone_call_only_routes_that_exist(routes):
    paths = {path for _, path in routes}
    missing = []
    checked = 0
    for file in source_files():
        text = file.read_text(encoding="utf-8")
        where = file.relative_to(REPO).as_posix()
        # A method and address together, as in api.call("POST", "/api/local/pairing").
        for method, path in re.findall(rf'"({METHODS})",\s*f?"(/api/[^"]+)"', text):
            checked += 1
            if (method, normalize(path)) not in routes:
                missing.append(f"{where}: {method} {path}")
        # Any other address in a string, as in PAIR_PATH = '/api/pair' or f"{base}/api/health":
        # the path must exist for some method. (Comments that mention an address are skipped.)
        for quote in "\"'`":
            for path in re.findall(rf"{quote}[^{quote}\n]*?(/api/[^{quote}\n]*){quote}", text):
                checked += 1
                if normalize(path) not in paths:
                    missing.append(f"{where}: {path}")
    assert checked > 10
    assert not missing, "These call routes the server doesn't have:\n" + "\n".join(missing)
