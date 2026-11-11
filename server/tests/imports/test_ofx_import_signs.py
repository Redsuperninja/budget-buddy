"""OFX card-sign checks in depth: bank types vs amounts, flip on a non-card, a flipped re-import.
Every file is made up."""

from ofx_helpers import card_many, ok, send, sgml, transaction, txns
from ofx_helpers import checking as statement

BACKWARDS = card_many(
    [("C1", "DEBIT", "30.00", "FAKE SHOP"), ("C2", "DEBIT", "20.00", "FAKE CAFE")]
    + [("C3", "CREDIT", "-50.00", "PAYMENT THANK YOU")]
)


def card(make_account) -> int:
    return make_account(name="Fake Card", kind="credit_card")["id"]


def flagged(client, account, lines) -> bool:
    return ok(send(client, account, card_many(lines)))["looks_flipped"]


def test_flip_on_a_checking_account_is_refused_and_nothing_is_imported(client, checking):
    file = sgml(statement([transaction("A", "-12.50")]))
    for action in ("preview", "commit"):
        extra = {"confirm_account": "true"} if action == "commit" else {}
        r = send(client, checking, file, action, flip_sign="true", **extra)
        assert r.status_code == 422 and r.json()["error"]["code"] == "flip_not_for_this_account"
        assert "credit card" in r.json()["error"]["message"]
    assert txns(client, checking) == []
    ok(send(client, checking, file, "commit", confirm_account="true", flip_sign="false"))
    assert [t["amount_cents"] for t in txns(client, checking)] == [-1250]


def test_payment_words_with_flipped_signs_are_flagged_despite_consistent_types(
    client, make_account
):
    # types say "fine" (CREDIT positive...) but the payments are money out
    lines = [(f"P{i}", "CREDIT", "50.00", "SHOP") for i in range(3)]
    lines += [("P9", "DEBIT", "-50.00", "PAYMENT THANK YOU")] * 1
    lines += [("P8", "DEBIT", "-40.00", "AUTOPAY PAYMENT")]
    assert flagged(client, card(make_account), lines) is True


def test_charges_typed_credit_with_negative_amounts_are_flagged(client, make_account):
    lines = [(f"T{i}", "CREDIT", "-10.00", f"SHOP {i}") for i in range(4)]
    assert flagged(client, card(make_account), lines) is True


def test_one_typed_row_among_many_untyped_rows_does_not_decide(client, make_account):
    lines = [("U0", "DEBIT", "5.00", "FAKE SHOP")]
    lines += [(f"U{i}", "", f"-{i}.00", f"FAKE SHOP {i}") for i in range(1, 8)]
    assert flagged(client, card(make_account), lines) is False


def test_a_tie_between_type_counts_falls_back_to_the_amounts(client, make_account):
    tied = [
        ("A1", "DEBIT", "5.00", "SHOP A"),
        ("A2", "CREDIT", "6.00", "SHOP B"),
        ("A3", "DEBIT", "-7.00", "SHOP C"),
        ("A4", "CREDIT", "-8.00", "SHOP D"),
    ]
    assert flagged(client, card(make_account), tied) is False  # amounts are split: no flag
    more = tied + [(f"A{i}", "", f"{i}.00", f"SHOP {i}") for i in range(5, 40)]
    assert flagged(client, card(make_account), more) is True  # 80%+ positive decides


def test_a_correct_file_with_refunds_typed_credit_and_a_big_payment_is_not_flagged(
    client, make_account
):
    lines = [(f"R{i}", "CREDIT", "9.00", f"FAKE REFUND {i}") for i in range(3)]
    lines += [
        ("R7", "DEBIT", "-12.00", "FAKE SHOP"),
        ("R8", "CREDIT", "900.00", "PAYMENT THANK YOU"),
    ]
    assert flagged(client, card(make_account), lines) is False


def test_reimporting_a_flipped_file_unflipped_says_the_signs_differ(client, make_account):
    account = card(make_account)
    ok(send(client, account, BACKWARDS, "commit", confirm_account="true", flip_sign="true"))
    body = ok(send(client, account, BACKWARDS, flip_sign="false"))
    assert (body["invalid_rows"], body["new_rows"]) == (3, 0)
    problem = body["rows"][0]["problem"]
    assert "signs differ" in problem and "flipping" in problem
    assert "different amount" not in problem
    refused = send(client, account, BACKWARDS, "commit", flip_sign="false")
    assert refused.json()["error"]["code"] == "invalid_rows"
    done = ok(
        send(client, account, BACKWARDS, "commit", flip_sign="false", skip_invalid_rows="true")
    )
    assert done["imported"] == 0
    assert [t["amount_cents"] for t in txns(client, account)] == [-3000, -2000, 5000]
