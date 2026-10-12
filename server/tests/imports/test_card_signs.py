"""A credit card file that lists charges as positive numbers is read the right way round, so the
card shows what you owe and its payment pairs with the checking side. Every file here is made up."""

import pytest
from csv_helpers import ok, send, txns

from app.services.imports.card_signs import looks_flipped

CARD_FILE = (
    "Date,Description,Amount\r\n"
    "10/01/2026,FAKE GROCERY,120.00\r\n"
    "10/02/2026,FAKE AIRLINE,250.00\r\n"
    "10/05/2026,PAYMENT THANK YOU,-300.00\r\n"
)
CHECKING_FILE = "Date,Description,Amount\r\n10/04/2026,FAKE CARD AUTOPAY PAYMENT,-300.00\r\n"


@pytest.fixture
def card(make_account) -> int:
    return make_account(name="Fake Card", kind="credit_card")["id"]


def test_the_preview_flips_and_says_so(client, card):
    preview = ok(send(client, card, CARD_FILE))
    assert preview["mapping"]["flip_sign"] is True
    assert "flipped" in preview["message"]
    assert [r["amount_cents"] for r in preview["rows"]] == [-12000, -25000, 30000]


def test_the_card_shows_what_you_owe_and_its_payment_pairs(client, card, make_account):
    checking = make_account(name="Fake Checking", kind="checking")["id"]
    ok(send(client, checking, CHECKING_FILE, "commit"))
    ok(send(client, card, CARD_FILE, "commit"))

    balance = client.get(f"/api/local/accounts/{card}").json()["balance_cents"]
    assert balance == -7000  # $370 charged, $300 paid: $70 owed
    payment = next(t for t in txns(client, card) if t["description"] == "PAYMENT THANK YOU")
    assert payment["kind"] == "transfer"
    waiting = client.get("/api/local/transactions", params={"uncategorized": "true"}).json()
    assert all("PAYMENT" not in t["description"] for t in waiting["items"])


def test_a_file_the_right_way_round_is_left_alone(client, card):
    right = CARD_FILE.replace(",120.00", ",-120.00").replace(",250.00", ",-250.00")
    right = right.replace(",-300.00", ",300.00")
    preview = ok(send(client, card, right))
    assert (preview["mapping"]["flip_sign"], preview["message"]) == (False, None)


def test_your_own_choice_wins(client, card):
    preview = ok(send(client, card, CARD_FILE, flip_sign=False))
    assert preview["mapping"]["flip_sign"] is False
    assert preview["rows"][0]["amount_cents"] == 12000


def test_only_credit_cards_are_checked(client, checking):
    preview = ok(send(client, checking, CARD_FILE))
    assert preview["mapping"]["flip_sign"] is False


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        # All charges positive: upside down.
        ([("FAKE STORE", 1000), ("FAKE CAFE", 500), ("FAKE GAS", 4000)], True),
        ([("FAKE STORE", -1000), ("FAKE CAFE", -500), ("FAKE REFUND", 300)], False),
        ([("FAKE STORE", 1000), ("FAKE CAFE", 500)], False),  # too few to tell
        ([("FAKE STORE", -1000), ("AUTOPAY PAYMENT", 5000)], False),
        ([("FAKE STORE", 1000), ("AUTOPAY PAYMENT", -5000)], True),
    ],
)
def test_what_looks_flipped(rows, expected):
    assert looks_flipped(rows) is expected
