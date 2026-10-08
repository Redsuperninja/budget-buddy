"""Other deductions API (roadmap #13). Fake data only."""

import pytest
from crypto_helpers import raw_rows

DEDUCTIONS = "/api/local/deductions"


def add(client, status=201, **body):
    body = {"tax_year": 2026, "kind": "medical", "amount": "120.00", **body}
    response = client.post(DEDUCTIONS, json=body)
    assert response.status_code == status, response.text
    return response.json()


def test_add_list_edit_delete(client):
    first = add(client, description="  Dentist ", date="2026-03-02")
    assert (first["amount_cents"], first["description"], first["kind"]) == (
        12_000,
        "Dentist",
        "medical",
    )
    undated = add(client, kind="ira", amount=None, amount_cents=700_000)
    add(client, tax_year=2025, kind="property_tax")

    listed = client.get(DEDUCTIONS, params={"tax_year": 2026}).json()
    assert [d["id"] for d in listed] == [first["id"], undated["id"]]  # dated first, then undated

    edited = client.patch(f"{DEDUCTIONS}/{first['id']}", json={"amount": "150.5"})
    assert edited.json()["amount_cents"] == 15_050
    assert client.delete(f"{DEDUCTIONS}/{first['id']}").status_code == 204
    assert client.get(f"{DEDUCTIONS}/{first['id']}").status_code == 404


@pytest.mark.parametrize(
    ("body", "text"),
    [
        ({"amount": "-5"}, "can't be negative"),
        ({"amount": None, "amount_cents": None}, "An amount is required"),
        ({"amount_cents": 100}, "not both"),
        ({"date": "2025-12-31"}, "in the tax year"),
        ({"tax_year": 1999}, "tax_year"),
        ({"kind": "boat"}, "kind"),
    ],
)
def test_checks(client, body, text):
    response = client.post(
        DEDUCTIONS, json={"tax_year": 2026, "kind": "medical", "amount": "1", **body}
    )
    assert response.status_code == 422
    assert text in response.text


def test_edit_keeps_date_in_tax_year(client):
    made = add(client, date="2026-05-01")
    moved = client.patch(f"{DEDUCTIONS}/{made['id']}", json={"tax_year": 2025})
    assert moved.status_code == 422
    assert "in the tax year" in moved.json()["error"]["message"]
    both = client.patch(f"{DEDUCTIONS}/{made['id']}", json={"tax_year": 2025, "date": "2025-05-01"})
    assert both.status_code == 200


def test_unknown_receipt(client):
    response = client.post(
        DEDUCTIONS, json={"tax_year": 2026, "kind": "hsa", "amount": "1", "receipt_id": 999}
    )
    assert response.status_code == 404


def test_list_needs_a_year(client):
    assert client.get(DEDUCTIONS).status_code == 422


def test_description_is_encrypted_at_rest(client, data_dir):
    made = add(client, description="Fake clinic visit")
    assert client.get(f"{DEDUCTIONS}/{made['id']}").json()["description"] == "Fake clinic visit"
    (stored,) = raw_rows(data_dir, "SELECT description FROM deductions")[0]
    assert isinstance(stored, bytes) and b"clinic" not in stored
