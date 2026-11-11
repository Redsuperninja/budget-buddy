"""Bank OFX import: preview, save, duplicates, account match, history. Every file is made up."""

import pytest
from ofx_helpers import card_xml, ok, send, sgml, transaction, txns
from ofx_helpers import checking as statement

OFX = "application/x-ofx"


def two(*extra):
    return sgml(statement([transaction(), transaction("FAKE002", "2000.00", name="PAY"), *extra]))


def test_preview_saves_nothing(client, checking):
    body = ok(send(client, checking, two()))
    assert (body["new_rows"], body["duplicate_rows"], body["total_rows"]) == (2, 0, 2)
    assert body["chosen"] == 1 and body["needs_confirmation"] is True
    assert body["statements"] == [
        {"number": 1, "last4": "6789", "kind": "CHECKING", "transactions": 2}
    ]
    assert [r["amount_cents"] for r in body["rows"]] == [-1250, 200000]
    assert body["rows"][0]["date"] == "2026-01-05"
    assert txns(client, checking) == []


def test_save_needs_confirmation_then_saves_last4_and_history(client, checking):
    refused = send(client, checking, two(), "commit", file_name="fake.ofx")
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "confirm_account"
    assert txns(client, checking) == []
    done = ok(send(client, checking, two(), "commit", confirm_account="true", file_name="fake.ofx"))
    assert (done["imported"], done["account_saved"]) == (2, True)
    rows = txns(client, checking)
    assert [t["amount_cents"] for t in rows] == [-1250, 200000]
    assert client.get("/api/local/accounts").json()[0]["last4"] == "6789"
    history = client.get("/api/local/imports").json()
    assert [(h["kind"], h["rows_added"], h["file_name"]) for h in history] == [
        ("bank", 2, "fake.ofx")
    ]


def test_reimport_and_overlap_add_nothing_new(client, checking):
    ok(send(client, checking, two(), "commit", confirm_account="true"))
    again = ok(send(client, checking, two(), "commit"))
    assert (again["imported"], again["skipped_duplicates"], again["account_saved"]) == (0, 2, False)
    later = sgml(
        statement([transaction("FAKE002", "2000.00", name="PAY"), transaction("FAKE003", "-5.00")])
    )
    overlap = ok(send(client, checking, later, "commit"))
    assert (overlap["imported"], overlap["skipped_duplicates"]) == (1, 1)
    assert len(txns(client, checking)) == 3
    assert len(client.get("/api/local/imports").json()) == 2  # the empty re-import isn't recorded


def test_same_id_in_another_account_is_not_a_duplicate(client, checking, make_account):
    other = make_account(name="Other")["id"]
    ok(send(client, checking, two(), "commit", confirm_account="true"))
    assert ok(send(client, other, two(), "commit", confirm_account="true"))["imported"] == 2


def test_reused_id_with_another_amount_is_flagged(client, checking):
    ok(send(client, checking, two(), "commit", confirm_account="true"))
    changed = sgml(statement([transaction("FAKE001", "-99.00")]))
    body = ok(send(client, checking, changed))
    assert (body["invalid_rows"], body["new_rows"]) == (1, 0)
    assert "different amount" in body["rows"][0]["problem"]
    refused = send(client, checking, changed, "commit")
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "invalid_rows"
    skipped = ok(send(client, checking, changed, "commit", skip_invalid_rows="true"))
    assert (skipped["imported"], skipped["skipped_invalid"]) == (0, 1)


def test_wrong_account_is_stopped(client, make_account):
    account = make_account(last4="1111")["id"]
    for action in ("preview", "commit"):
        response = send(client, account, two(), action)
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "wrong_account"
        assert "ending 6789" in error["message"] and "1111" in error["message"]
        assert "999999999" not in error["message"]  # the bank id is never trusted or shown
    assert txns(client, account) == []


def test_matching_saved_last4_needs_no_confirmation(client, make_account):
    account = make_account(last4="6789")["id"]
    assert ok(send(client, account, two()))["needs_confirmation"] is False
    assert ok(send(client, account, two(), "commit"))["imported"] == 2


def two_accounts() -> bytes:
    first = statement([transaction()], acct="0000000001111")
    second = statement([transaction("FAKE777", "-7.00")], acct="0000000002222")
    inner = second[second.index("<BANKMSGSRSV1>") : second.index("</BANKMSGSRSV1>")]
    return sgml(
        first.replace("</BANKMSGSRSV1>", inner[len("<BANKMSGSRSV1>") :] + "</BANKMSGSRSV1>")
    )


def test_several_accounts_in_a_file_need_a_choice(client, checking):
    body = ok(send(client, checking, two_accounts()))
    assert body["chosen"] is None and len(body["statements"]) == 2
    assert "Choose which one" in body["message"]
    refused = send(client, checking, two_accounts(), "commit", confirm_account="true")
    assert refused.json()["error"]["code"] == "choose_statement"
    done = ok(send(client, checking, two_accounts(), "commit", statement=2, confirm_account="true"))
    assert done["imported"] == 1
    assert txns(client, checking)[0]["amount_cents"] == -700
    assert client.get("/api/local/accounts").json()[0]["last4"] == "2222"


def test_saved_last4_picks_its_statement_automatically(client, make_account):
    account = make_account(last4="1111")["id"]
    body = ok(send(client, account, two_accounts()))
    assert body["chosen"] == 1
    assert (
        send(client, account, two_accounts(), statement=2).json()["error"]["code"]
        == "wrong_account"
    )
    assert (
        send(client, account, two_accounts(), statement=9).json()["error"]["code"]
        == "no_such_statement"
    )


def test_card_statement_keeps_the_banks_signs(client, make_account):
    card = make_account(name="Fake Card", kind="credit_card")["id"]
    ok(send(client, card, card_xml("-30.00"), "commit", confirm_account="true"))
    row = txns(client, card)[0]
    assert (row["amount_cents"], row["description"]) == (
        -3000,
        "FAKE & SONS",
    )  # a charge is money out


@pytest.mark.parametrize(
    ("body", "content_type", "status", "code"),
    [
        (two(), "application/json", 415, "not_an_ofx"),
        (two(), "image/png", 415, "not_an_ofx"),
        (b"\x89PNG\r\n\x1a\n\x00\x00", OFX, 400, "unreadable_file"),
        (b"", OFX, 400, "unreadable_file"),
        (b"a,b,c\n1,2,3\n", "text/plain", 400, "unreadable_file"),
    ],
)
def test_garbage_is_refused_in_plain_english(client, checking, body, content_type, status, code):
    response = send(client, checking, body, content_type=content_type)
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert "Traceback" not in error["message"] and "OfxError" not in error["message"]


def test_oversized_file_is_refused(client, checking, monkeypatch):
    from app.services.imports import ofx_parsing

    monkeypatch.setattr(ofx_parsing, "MAX_BYTES", 100)
    response = send(client, checking, two())
    assert response.status_code == 413 and response.json()["error"]["code"] == "file_too_large"


def test_xxe_style_file_is_just_text(client, checking):
    xxe = (
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKACCTFROM><ACCTID>12346789</ACCTID></BANKACCTFROM>"
        "<BANKTRANLIST><STMTTRN><DTPOSTED>20260105</DTPOSTED><TRNAMT>-1.00</TRNAMT>"
        "<FITID>X1</FITID><NAME>&e;</NAME></STMTTRN></BANKTRANLIST></STMTRS></STMTTRNRS>"
        "</BANKMSGSRSV1></OFX>"
    )
    body = ok(send(client, checking, xxe))
    assert body["rows"][0]["description"] == "&e;"  # never expanded or fetched


def test_unknown_account_is_404(client):
    assert send(client, 9999, two()).status_code == 404


def test_import_is_sorted_by_rules_and_can_be_undone(client, checking):
    ok(send(client, checking, two(), "commit", confirm_account="true", file_name="a.ofx"))
    import_id = client.get("/api/local/imports").json()[0]["id"]
    assert client.delete(f"/api/local/imports/{import_id}").status_code == 204
    assert txns(client, checking) == []
