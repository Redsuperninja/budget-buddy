"""Match everything again: data imported before the finders knew better gets matched now. To stand
in for an older data set, the file is imported with the finders switched off. Fake numbers only."""

import pytest
from csv_helpers import ok, send

from app.services import bank_trades, dividend_matching
from app.services.imports import csv_import
from app.services.ledger import match_again

AGAIN = "/api/local/transactions/match-again"
TRADE = "FAKECO INC UNSOLICITED WE ARE ACTING AS PRINCIPAL COMMISSION FIELD IS A COMMISSION"
OTHER = "OTHERCO INC UNSOLICITED WE ARE ACTING AS PRINCIPAL COMMISSION FIELD IS A COMMISSION"
SWEEP_IN = "FAKE DEPOSIT SWEEP INTRA-DAY WITHDRWAL"
SWEEP_OUT = "FAKE DEPOSIT SWEEP INTRA-DAY DEPOSIT"
BROKERAGE_FILE = (
    "Date,Description,Amount\r\n"
    "10/01/2026,ONLINE TRANSFER FROM CHECKING,1000.00\r\n"
    f"10/02/2026,{TRADE},-500.00\r\n"
    f"10/02/2026,{OTHER},-300.00\r\n"
    f"10/02/2026,{SWEEP_IN},800.00\r\n"
    "10/03/2026,FAKECO INC CASH DIV ON 10 SHS,12.34\r\n"
    f"10/03/2026,{SWEEP_OUT},-12.34\r\n"
)
CHECKING_FILE = "Date,Description,Amount\r\n10/01/2026,ONLINE TRANSFER TO BROKERAGE,-1000.00\r\n"


def waiting(client) -> list[str]:
    items = client.get("/api/local/transactions", params={"uncategorized": "true"}).json()
    return sorted(t["description"] for t in items["items"])


@pytest.fixture
def old_data(client, make_account, monkeypatch) -> None:
    """Imported as if Budget Buddy had no finders yet."""
    nothing = {"find_dividends": dividend_matching.Found(), "find_trades": bank_trades.Found()}
    for name, empty in nothing.items():
        monkeypatch.setattr(csv_import, name, lambda *_, empty=empty: empty)
    monkeypatch.setattr(csv_import, "match_transfers", lambda *_: 0)
    checking = make_account(name="Fake Checking", kind="checking")["id"]
    brokerage = make_account(name="Fake Brokerage", kind="brokerage")["id"]
    ok(send(client, checking, CHECKING_FILE, "commit"))
    ok(send(client, brokerage, BROKERAGE_FILE, "commit"))
    monkeypatch.undo()


def test_everything_is_matched_again(client, old_data):
    assert len(waiting(client)) == 7  # nothing sorted yet

    result = client.post(AGAIN).json()
    assert result == {"dividends_found": 1, "trades_found": 2, "sweeps_linked": 2,
                      "transfers_linked": 1}  # fmt: skip
    assert waiting(client) == []
    trades = client.get("/api/local/stocks/bank-trades").json()["items"]
    assert len({t["sweep_transaction_id"] for t in trades}) == 1  # one sweep for both buys


def test_running_it_twice_changes_nothing(client, old_data):
    client.post(AGAIN)
    again = client.post(AGAIN).json()
    assert again == {
        "dividends_found": 0,
        "trades_found": 0,
        "sweeps_linked": 0,
        "transfers_linked": 0,
    }
    assert waiting(client) == []


def test_your_decisions_stay(client, old_data):
    client.post(AGAIN)
    [dividend] = client.get("/api/local/dividends/2026").json()["dividends"]
    assert client.post(f"/api/local/dividends/{dividend['id']}/dismiss").status_code == 204
    assert client.post(AGAIN).json()["dividends_found"] == 0
    assert client.get("/api/local/dividends/2026").json()["dividends"] == []


def trade_sweeps(client) -> set[int | None]:
    items = client.get("/api/local/stocks/bank-trades").json()["items"]
    return {t["sweep_transaction_id"] for t in items}


def test_a_link_the_new_rules_wouldnt_make_is_kept(client, old_data, monkeypatch):
    client.post(AGAIN)
    sweeps = trade_sweeps(client)
    # As if today's rules couldn't find that combined sweep any more.
    monkeypatch.setattr(bank_trades, "link_combined", lambda _session: 0)
    assert client.post(AGAIN).json()["sweeps_linked"] == 0
    assert trade_sweeps(client) == sweeps
    assert waiting(client) == []


def test_one_run_at_a_time(client):
    with match_again._RUNNING:
        busy = client.post(AGAIN)
    assert (busy.status_code, busy.json()["error"]["code"]) == (409, "busy")
