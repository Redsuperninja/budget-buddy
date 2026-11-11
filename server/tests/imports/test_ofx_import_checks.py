"""OFX import safety checks: edited rows, backwards card signs, look-alike rows, per-account
problems, zero amounts, time zones and the steps that follow an import. Every file is made up."""

import datetime as dt

from ofx_helpers import card_many, join_statements, ok, send, sgml, transaction, txns
from ofx_helpers import checking as statement

from app.services.imports import ofx_parsing

BACKWARDS = card_many(
    [
        ("C1", "DEBIT", "30.00", "FAKE SHOP"),
        ("C2", "DEBIT", "20.00", "FAKE CAFE"),
        ("C3", "CREDIT", "-50.00", "PAYMENT THANK YOU"),
    ]
)
RIGHT_WAY = card_many(
    [
        ("C1", "DEBIT", "-30.00", "FAKE SHOP"),
        ("C2", "DEBIT", "-20.00", "FAKE CAFE"),
        ("C3", "CREDIT", "50.00", "PAYMENT THANK YOU"),
    ]
)


def card(make_account) -> int:
    return make_account(name="Fake Card", kind="credit_card")["id"]


def test_a_row_edited_here_is_flagged_without_blaming_the_bank(client, checking):
    file = sgml(statement([transaction("FAKE001", "-12.50")]))
    ok(send(client, checking, file, "commit", confirm_account="true"))
    row = txns(client, checking)[0]
    edited = client.patch(f"/api/local/transactions/{row['id']}", json={"amount_cents": -9999})
    assert edited.status_code == 200, edited.text
    body = ok(send(client, checking, file))
    assert (body["invalid_rows"], body["new_rows"]) == (1, 0)
    problem = body["rows"][0]["problem"]
    assert "already here with a different amount" in problem and "edited" in problem
    assert "bank" not in problem
    refused = send(client, checking, file, "commit")
    assert refused.json()["error"]["code"] == "invalid_rows"
    skipped = ok(send(client, checking, file, "commit", skip_invalid_rows="true"))
    assert (skipped["imported"], skipped["skipped_invalid"]) == (0, 1)
    assert txns(client, checking)[0]["amount_cents"] == -9999  # the edit is kept


def test_backwards_card_file_warns_and_waits_for_a_choice(client, make_account):
    account = card(make_account)
    body = ok(send(client, account, BACKWARDS))
    assert body["looks_flipped"] is True and body["flip_sign"] is False
    assert "positive numbers" in body["message"]
    assert [r["amount_cents"] for r in body["rows"]] == [3000, 2000, -5000]  # as the file says
    refused = send(client, account, BACKWARDS, "commit", confirm_account="true")
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "choose_card_signs"
    assert txns(client, account) == []


def test_backwards_card_file_flipped_by_choice(client, make_account):
    account = card(make_account)
    body = ok(send(client, account, BACKWARDS, flip_sign="true"))
    assert body["looks_flipped"] is False and body["flip_sign"] is True
    ok(send(client, account, BACKWARDS, "commit", confirm_account="true", flip_sign="true"))
    assert [t["amount_cents"] for t in txns(client, account)] == [-3000, -2000, 5000]


def test_backwards_card_file_kept_as_is_by_choice(client, make_account):
    account = card(make_account)
    ok(send(client, account, BACKWARDS, "commit", confirm_account="true", flip_sign="false"))
    assert [t["amount_cents"] for t in txns(client, account)] == [3000, 2000, -5000]


def test_correct_card_file_has_no_warning(client, make_account):
    account = card(make_account)
    body = ok(send(client, account, RIGHT_WAY))
    assert body["looks_flipped"] is False
    assert "positive numbers" not in body["message"]  # only the account digits note
    ok(send(client, account, RIGHT_WAY, "commit", confirm_account="true"))
    assert [t["amount_cents"] for t in txns(client, account)] == [-3000, -2000, 5000]


def test_backwards_card_without_bank_types_is_caught_by_the_amounts(client, make_account):
    lines = [(f"X{i}", "", f"{i + 1}.00", f"FAKE SHOP {i}") for i in range(4)]
    assert ok(send(client, card(make_account), card_many(lines)))["looks_flipped"] is True


def test_checking_file_is_never_asked_about_signs(client, checking):
    body = ok(send(client, checking, sgml(statement([transaction("A", "10.00")]))))
    assert body["looks_flipped"] is False


def test_fresh_ids_for_the_same_purchases_show_as_possible_duplicates(client, checking):
    first = sgml(statement([transaction("A1", "-12.50"), transaction("A2", "-5.00")]))
    ok(send(client, checking, first, "commit", confirm_account="true"))
    again = sgml(statement([transaction("B1", "-12.50"), transaction("B2", "-7.00")]))
    body = ok(send(client, checking, again))
    assert body["possible_duplicate_rows"] == 1 and body["new_rows"] == 2
    assert [r["amount_cents"] for r in body["possible_duplicates"]] == [-1250]
    assert "earlier bank file" in body["message"] and "same date and amount" in body["message"]
    assert ok(send(client, checking, again, "commit"))["imported"] == 2  # never blocks


def test_notes_are_merged_with_the_account_confirmation(client, checking, add_txn):
    add_txn(checking, -1250, date="2026-01-05")
    file = sgml(statement([transaction("A1", "-12.50")]))
    body = ok(send(client, checking, file))
    assert body["needs_confirmation"] is True
    assert "no saved account digits" in body["message"]
    assert "same date and amount" in body["message"]
    assert ok(send(client, checking, file, "commit", confirm_account="true"))["imported"] == 1


def test_problems_belong_to_their_own_account(client, make_account):
    bad = transaction("BAD1", "abc")
    first = statement([transaction("F1"), bad], acct="0000000001111")
    second = statement(
        [transaction("S1"), transaction("S2", "-3.00"), transaction("BAD2", "abc")],
        acct="0000000002222",
    )
    nameless = statement([transaction("N1"), transaction("N2", "abc")], acct="")
    file = join_statements(first, second, nameless)
    account = make_account(name="Second")["id"]
    one = ok(send(client, account, file, statement=1))
    assert len(one["problems"]) == 1 and "Transaction 2 " in one["problems"][0]
    two = ok(send(client, account, file, statement=2))
    assert len(two["problems"]) == 1 and "Transaction 3 " in two["problems"][0]
    assert [r["row_number"] for r in two["rows"]] == [1, 2]
    # Account 2's own file is clean, so a bad row in account 1 and a nameless account don't count.
    clean = join_statements(
        first,
        statement([transaction("S1"), transaction("S2", "-3.00")], acct="0000000002222"),
        nameless,
    )
    done = ok(send(client, account, clean, "commit", statement=2, confirm_account="true"))
    assert (done["imported"], done["skipped_invalid"]) == (2, 0)
    third = make_account(name="Third")["id"]
    refused = send(client, third, file, "commit", statement=1, confirm_account="true")
    assert refused.json()["error"]["code"] == "invalid_rows"


def test_zero_amount_rows_are_skipped_quietly(client, checking):
    file = sgml(statement([transaction("Z1", "0.00"), transaction("Z2", "-4.00")]))
    body = ok(send(client, checking, file))
    assert (body["zero_rows"], body["new_rows"], body["invalid_rows"]) == (1, 1, 0)
    assert body["total_rows"] == 2 and [r["row_number"] for r in body["rows"]] == [2]
    done = ok(send(client, checking, file, "commit", confirm_account="true"))
    assert (done["imported"], done["skipped_zero"], done["skipped_invalid"]) == (1, 1, 0)


def test_the_stated_date_is_used_whatever_the_time_zone(client, checking):
    dates = [
        "20260105",
        "20260105120000.000[-5:EST]",
        "20260106235959[0:GMT]",
        "20261231230000[0:GMT]",
    ]
    file = sgml(statement([transaction(f"D{i}", "-1.00", date=d) for i, d in enumerate(dates)]))
    body = ok(send(client, checking, file))
    assert [r["date"] for r in body["rows"]] == [
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        "2026-12-31",
    ]


def test_parser_keeps_the_stated_date():
    for text in ("20260105", "20260105000000[-5:EST]", "20260105235959.999[0:GMT]"):
        assert ofx_parsing.parse_date(text) == dt.date(2026, 1, 5)
    # still Dec 31 in US zones, but the stated date is kept
    assert ofx_parsing.parse_date("20270101030000[0:GMT]") == dt.date(2027, 1, 1)


def test_later_steps_find_transfers_dividends_and_trades(client, make_account):
    checking = make_account(name="Fake Checking")["id"]
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    out = sgml(
        statement(
            [
                transaction("T1", "-500.00", name="ONLINE TRANSFER PAYMENT"),
                transaction("T2", "5.00", name="FAKECO CASH DIVIDEND"),
            ]
        )
    )
    into = sgml(
        statement(
            [transaction("T3", "500.00", name="ONLINE TRANSFER PAYMENT")], acct="0000000002222"
        )
    )
    first = ok(send(client, checking, out, "commit", confirm_account="true"))
    assert (first["transfers_matched"], first["dividends_found"]) == (0, 1)
    second = ok(send(client, savings, into, "commit", confirm_account="true"))
    assert second["transfers_matched"] >= 1
    assert {t["kind"] for t in txns(client, savings)} == {"transfer"}

    broker = make_account(name="Fake Broker", kind="brokerage")["id"]
    trade = sgml(
        statement(
            [
                transaction("B1", "-500.00", date="20260105", name="YOU BOUGHT FAKE FUND (FAKE)"),
                transaction(
                    "B2", "500.00", date="20260106", name="FAKE DEPOSIT SWEEP INTRA-DAY WITHDRWAL"
                ),
            ],
            acct="0000000003333",
        )
    )
    done = ok(send(client, broker, trade, "commit", confirm_account="true"))
    assert (done["trades_found"], done["trade_sweeps_linked"]) == (1, 1)
