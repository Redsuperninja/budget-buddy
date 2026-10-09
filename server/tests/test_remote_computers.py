"""Other computers on the home network (ADR-0009): join codes, the cookie, what they may do."""

import pytest
from fastapi.testclient import TestClient

from app.services import remote_computers as service

LAN_BASE = "http://192.168.1.20:8765"
CODE_URL = "/api/local/remote-computers/join-code"
JOIN = "/api/remote/join"


@pytest.fixture
def home(make_client) -> TestClient:
    """The Budget Buddy computer itself."""
    return make_client()


@pytest.fixture
def laptop(home) -> TestClient:
    """Another computer on the home network, opening the page at the home-network address."""
    return TestClient(
        home.app, client=("192.168.1.50", 50000), base_url=LAN_BASE, headers={"Origin": LAN_BASE}
    )


def new_code(home) -> str:
    response = home.post(CODE_URL)
    assert response.status_code == 200, response.text
    return response.json()["code"]


def join(laptop, code: str, name: str = "Fake laptop"):
    return laptop.post(JOIN, json={"code": code, "name": name})


def joined(home, laptop) -> TestClient:
    assert join(laptop, new_code(home)).status_code == 200
    laptop.headers["X-CSRF-Token"] = home.app.state.csrf_token
    return laptop


def code_of(response) -> str:
    return response.json()["error"]["code"]


def test_join_code_shows_the_address_and_a_readable_code(home):
    body = home.post(CODE_URL).json()
    assert body["address"] == "http://192.168.1.20:8765/"
    assert len(body["code"]) == 9 and body["code"][4] == "-"
    assert body["seconds_valid"] == 600


def test_a_computer_that_hasnt_joined_gets_nothing(laptop):
    response = laptop.get("/api/local/accounts")
    assert response.status_code == 403
    assert code_of(response) == "not_this_computer"


def test_joining_lets_the_computer_use_the_dashboard(home, laptop):
    laptop = joined(home, laptop)
    assert service.COOKIE_NAME in laptop.cookies
    assert laptop.get("/api/local/accounts").status_code == 200
    made = laptop.post("/api/local/accounts", json={"name": "Fake Checking", "kind": "checking"})
    assert made.status_code == 201
    # The page now carries the token.
    assert home.app.state.csrf_token in laptop.get("/").text


def test_code_is_case_and_dash_insensitive_and_works_once(home, laptop):
    code = new_code(home)
    assert join(laptop, code.lower().replace("-", " ")).status_code == 200
    again = join(laptop, code)
    assert again.status_code == 403
    assert code_of(again) == "wrong_code"


def test_five_wrong_codes_end_it(home, laptop):
    code = new_code(home)
    for _ in range(5):
        assert code_of(join(laptop, "WRONG-CODE")) == "wrong_code"
    assert code_of(join(laptop, code)) == "wrong_code"


def test_an_expired_code_is_refused(home, laptop):
    code = new_code(home)
    home.app.state.clock = lambda: 10**10
    assert code_of(join(laptop, code)) == "wrong_code"


def test_joining_is_rate_limited(home, laptop):
    new_code(home)
    home.app.state.join_limiter.limit = 2
    for _ in range(2):
        join(laptop, "WRONG-CODE")
    assert join(laptop, "WRONG-CODE").status_code == 429


def test_joining_needs_the_page_origin(home, laptop):
    code = new_code(home)
    response = laptop.post(
        JOIN, json={"code": code, "name": "x"}, headers={"Origin": "http://evil"}
    )
    assert response.status_code == 403
    assert code_of(response) == "bad_origin"


def test_writes_need_the_token_and_the_home_network_origin(home, laptop):
    laptop = joined(home, laptop)
    body = {"name": "Fake", "kind": "checking"}
    no_token = laptop.post("/api/local/accounts", json=body, headers={"X-CSRF-Token": "nope"})
    assert code_of(no_token) == "bad_origin"
    local_origin = laptop.post(
        "/api/local/accounts", json=body, headers={"Origin": "http://127.0.0.1:8765"}
    )
    assert code_of(local_origin) == "bad_origin"


@pytest.mark.parametrize(
    "path",
    [
        "/api/local/devices",
        "/api/local/remote-computers",
        "/api/local/csrf-token",
    ],
)
def test_a_joined_computer_cant_let_more_devices_in(home, laptop, path):
    laptop = joined(home, laptop)
    response = laptop.get(path)
    assert response.status_code == 403
    assert code_of(response) == "not_this_computer"


@pytest.mark.parametrize("path", [CODE_URL, "/api/local/pairing"])
def test_a_joined_computer_cant_make_codes(home, laptop, path):
    laptop = joined(home, laptop)
    assert laptop.post(path).status_code == 403


def test_a_computer_must_use_the_home_network_address(home, laptop):
    laptop = joined(home, laptop)
    response = laptop.get("/api/local/accounts", headers={"Host": "127.0.0.1:8765"})
    assert response.status_code == 403


def test_removing_a_computer_stops_it_at_once(home, laptop):
    laptop = joined(home, laptop)
    laptop.get("/api/local/accounts")  # seen once
    (computer,) = home.get("/api/local/remote-computers").json()
    assert computer["name"] == "Fake laptop"
    assert computer["last_seen_at"] is not None
    assert home.post(f"/api/local/remote-computers/{computer['id']}/remove").status_code == 204
    assert laptop.get("/api/local/accounts").status_code == 403
    assert home.get("/api/local/remote-computers").json() == []
    assert home.post(f"/api/local/remote-computers/{computer['id']}/remove").status_code == 404


def test_a_made_up_cookie_gets_nothing(laptop):
    laptop.cookies.set(service.COOKIE_NAME, "made-up")
    assert laptop.get("/api/local/accounts").status_code == 403


def test_network_stays_wanted_while_a_code_is_live_or_a_computer_joined(home, laptop):
    from sqlalchemy.orm import Session

    state = home.app.state

    def wanted() -> bool:
        with Session(state.engine) as session:
            return service.network_wanted(session, state.join_codes, state.clock())

    assert not wanted()
    code = new_code(home)
    assert wanted()
    join(laptop, code)
    assert wanted()  # the code is spent, but a computer joined


def test_normalize_code():
    assert service.normalize_code(" abcd-efgh ") == "ABCDEFGH"


def test_the_cookie_only_works_from_the_address_that_joined(home, laptop):
    laptop = joined(home, laptop)
    stolen = TestClient(home.app, client=("192.168.1.66", 50000), base_url=LAN_BASE)
    stolen.cookies.set(service.COOKIE_NAME, laptop.cookies[service.COOKIE_NAME])
    assert stolen.get("/api/local/accounts").status_code == 403
    (computer,) = home.get("/api/local/remote-computers").json()
    assert computer["joined_from"] == "192.168.1.50"


def test_the_cookie_runs_out(home, laptop, monkeypatch):
    laptop = joined(home, laptop)
    monkeypatch.setattr(service, "TOKEN_LIFETIME", service.dt.timedelta(seconds=-1))
    assert laptop.get("/api/local/accounts").status_code == 403


def test_a_bad_cookie_from_another_app_doesnt_lock_us_out(home, laptop):
    laptop = joined(home, laptop)
    token = laptop.cookies[service.COOKIE_NAME]
    laptop.cookies.clear()
    header = {"Cookie": f'x=1;; other="broken; {service.COOKIE_NAME}={token}'}
    assert laptop.get("/api/local/accounts", headers=header).status_code == 200


def test_every_dashboard_route_is_classified(data_dir):
    """Joined computers get an allow-list. A new /api/local area must be added to JOINED_AREAS on
    purpose, or stay this computer only by being listed here."""
    from app.main import create_app
    from app.remote_access import JOINED_AREAS

    this_computer_only = {"pairing", "devices", "remote-computers", "csrf-token", "instance"}

    def paths(routes):  # included routers are wrapped; their routes carry the full path
        for route in routes:
            inner = getattr(route, "original_router", None)
            yield from paths(inner.routes) if inner is not None else [getattr(route, "path", "")]

    areas = {p.split("/")[3] for p in paths(create_app().routes) if p.startswith("/api/local/")}
    assert areas == set(JOINED_AREAS) | this_computer_only
