"""The snapshot the server sends has exactly the shape of the contract's published example.

``check_shape`` and the snapshot builder are written by hand; this ties both to the example in
docs/api/sync-contract/05-snapshot.md, which the phone's tests also parse. Fake data only.
"""

from contract_example import contract_example, shape
from snapshot_helpers import TODAY, add, check_shape, days_ago, snapshot, txn

from app.models import Deduction, DeductionKind, Paycheck


def test_the_contract_example_passes_the_servers_shape_check():
    check_shape(contract_example())


def test_a_full_snapshot_has_the_same_fields_and_kinds_as_the_contract_example(phone):
    d = phone.dashboard
    account = d.post("/api/local/accounts", json={"name": "Everyday", "kind": "checking"}).json()
    needs = next(c for c in d.get("/api/local/categories").json() if c["group"] == "needs")
    d.patch(f"/api/local/categories/{needs['id']}", json={"budget_cents": 50_000})
    add(
        phone,
        txn(account["id"], days_ago(2), -2_000),  # no category: older, so not the first listed
        txn(account["id"], TODAY, -3_245, category_id=needs["id"]),
        Paycheck(
            pay_date=TODAY.replace(day=1),
            employer="Fake Employer Inc",
            gross_cents=300_000,
            net_cents=260_000,
        ),
        Deduction(tax_year=TODAY.year, kind=DeductionKind.MEDICAL, amount_cents=23_000),
    )

    s = snapshot(phone)

    check_shape(s)
    assert shape(s) == shape(contract_example())
