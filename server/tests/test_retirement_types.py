"""Retirement account types, and Roth IRA money counted toward the IRA limit. Fake data only."""

ACCOUNTS = "/api/local/accounts"


def ira_line(client, year=2026):
    limits = client.get(f"/api/local/retirement/{year}").json()["limits"]
    return next(x for x in limits if x["name"] == "IRA")


def test_only_retirement_accounts_have_a_type(client, make_account):
    roth = make_account(name="Fake Roth", kind="retirement", retirement_type="roth_ira")
    assert roth["retirement_type"] == "roth_ira"
    refused = client.post(
        ACCOUNTS, json={"name": "X", "kind": "checking", "retirement_type": "401k"}
    )
    assert refused.status_code == 422
    assert "Only a retirement account" in refused.json()["error"]["message"]

    changed = client.patch(f"{ACCOUNTS}/{roth['id']}", json={"retirement_type": "401k"})
    assert changed.json()["retirement_type"] == "401k"
    moved = client.patch(f"{ACCOUNTS}/{roth['id']}", json={"kind": "brokerage"})
    assert (moved.json()["kind"], moved.json()["retirement_type"]) == ("brokerage", None)
    wrong = client.patch(f"{ACCOUNTS}/{roth['id']}", json={"retirement_type": "roth_ira"})
    assert wrong.status_code == 422


def test_money_into_a_roth_ira_counts_toward_the_ira_limit(client, make_account, add_txn):
    checking = make_account()["id"]
    roth = make_account(name="Fake Roth", kind="retirement", retirement_type="roth_ira")["id"]
    traditional = make_account(
        name="Fake IRA", kind="retirement", retirement_type="traditional_ira"
    )["id"]
    out = add_txn(checking, -100_000, date="2026-02-01", description="Fake move")
    into = add_txn(roth, 100_000, date="2026-02-01", description="Fake move")
    linked = client.post(
        f"/api/local/transactions/{into['id']}/transfer", json={"other_id": out["id"]}
    )
    assert linked.status_code == 200, linked.text
    add_txn(roth, 50_000, date="2026-03-01", description="CONTRIBUTION 2026")
    add_txn(roth, 900_000, date="2026-03-02", description="ROLLOVER CONTRIBUTION")  # doesn't count
    add_txn(roth, 1_000, date="2026-03-03", description="FAKE FUND DIVIDEND")  # doesn't count
    add_txn(roth, 70_000, date="2025-12-30", description="CONTRIBUTION 2025")  # another year
    add_txn(traditional, 20_000, date="2026-03-01", description="CONTRIBUTION")  # a deduction's job
    assert ira_line(client)["contributed_cents"] == 150_000
    assert "marked Roth IRA" in ira_line(client)["note"]
