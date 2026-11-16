"""The statement balance a preview offers for Match your bank's balance. Every file is made up."""

from ofx_helpers import card_many, card_xml, ok, send, sgml, txns
from ofx_helpers import checking as statement

BACKWARDS_LINES = [("C1", "DEBIT", "30.00", "FAKE SHOP"), ("C2", "DEBIT", "20.00", "FAKE CAFE")] + [
    ("C3", "CREDIT", "-50.00", "PAYMENT THANK YOU")
]


def with_balance(card_file: str, amount: str) -> str:
    return card_file.replace(
        "</CCSTMTRS>",
        f"<LEDGERBAL><BALAMT>{amount}</BALAMT><DTASOF>20260106</DTASOF></LEDGERBAL></CCSTMTRS>",
    )


def test_checking_preview_offers_the_balance_and_date_and_changes_nothing(client, checking):
    body = ok(send(client, checking, sgml(statement())))
    assert body["statement_balance"] == {"balance_cents": 123456, "date": "2026-01-10"}
    assert txns(client, checking) == []


def test_a_file_without_a_balance_offers_none(client, checking):
    file = statement().replace("<LEDGERBAL><BALAMT>1234.56<DTASOF>20260110120000</LEDGERBAL>", "")
    assert ok(send(client, checking, sgml(file)))["statement_balance"] is None


def test_card_balance_owed_is_offered_negative_as_the_file_has_it(client, make_account):
    account = make_account(name="Fake Card", kind="credit_card")["id"]
    body = ok(send(client, account, card_xml()))
    assert body["statement_balance"] == {"balance_cents": -3000, "date": "2026-01-06"}


def test_flipped_card_file_offers_nothing_until_chosen_then_matches_the_rows(client, make_account):
    account = make_account(name="Fake Card", kind="credit_card")["id"]
    file = with_balance(card_many(BACKWARDS_LINES), "10.00")  # file writes 10.00 owed
    held = ok(send(client, account, file))
    assert held["looks_flipped"] and held["statement_balance"] is None
    flipped = ok(send(client, account, file, flip_sign="true"))
    assert flipped["statement_balance"] == {"balance_cents": -1000, "date": "2026-01-06"}
    kept = ok(send(client, account, file, flip_sign="false"))
    assert kept["statement_balance"]["balance_cents"] == 1000


def test_the_offered_balance_is_what_the_balance_route_accepts(client, make_account):
    account = make_account(name="Fake Card", kind="credit_card")["id"]
    offered = ok(send(client, account, card_xml()))["statement_balance"]
    ok(send(client, account, card_xml(), "commit", confirm_account="true"))
    r = client.post(f"/api/local/accounts/{account}/balance", json=offered)
    assert r.status_code == 200 and r.json()["adjustment_cents"] == 0
    assert r.json()["balance_now_cents"] == -3000
