"""Fill a TEST Home Base with made-up demo data, through its normal API.

Everything here is fake: no real names, employers, charities or accounts. Dates are relative to
today, so the last three months always have activity. Run it via scripts/testing/load-demo-data.ps1.

Only talks to 127.0.0.1 on the test port (8766 by default), never the real Home Base on 8765.
"""

import argparse
import datetime as dt
import sys

from _local_api import ApiError, LocalApi
from _testguard import refuse_unless_test_server

DEMO_CHECKING = "Demo Everyday Checking"
# Everyday spending changes a little from month to month (percent of the listed amount, by
# months back), so the Home charts that compare months have something to show. Bills like rent
# stay the same.
EVERYDAY = {"Groceries", "Transportation", "Dining Out", "Shopping", "Entertainment", "Utilities"}
MONTH_PERCENT = {2: 112, 1: 94, 0: 103}


def months_back(today: dt.date, n: int) -> dt.date:
    """The 1st of the month n months before today's month."""
    year, month = today.year, today.month - n
    while month < 1:
        year, month = year - 1, month + 12
    return dt.date(year, month, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    port = parser.parse_args().port
    reason = refuse_unless_test_server(port)
    if reason:
        print(reason)
        return 2

    api = LocalApi(f"http://127.0.0.1:{port}")
    try:
        api.call("GET", "/api/health")
    except ApiError:
        print(f"The test Home Base isn't running on port {port}.")
        print("Start it first with scripts\\testing\\start-test-server.ps1 (in its own window).")
        return 1

    try:
        accounts = api.items("/api/local/accounts")
        if any(not a["name"].startswith("Demo ") for a in accounts):
            print(
                "Refusing: this Home Base has accounts that aren't demo data. Demo data only"
            )
            print(
                "goes into an empty test Home Base (scripts\\testing\\start-test-server.ps1 -Reset)."
            )
            return 2
        if any(a["name"] == DEMO_CHECKING for a in accounts):
            print(
                "Demo data is already loaded. To start over: scripts\\testing\\start-test-server.ps1 -Reset"
            )
            return 0
        load(api, dt.date.today())  # noqa: DTZ011 -- the tester's local calendar date is what we want
    except ApiError as exc:
        print(f"Something went wrong loading demo data: {exc.method} {exc.path}: {exc}")
        return 1
    print(f"Done. Open http://127.0.0.1:{port}/ in your browser to look around.")
    return 0


def load(api: LocalApi, today: dt.date) -> None:
    print("Adding demo accounts...")
    acct = {}
    for name, kind in [
        (DEMO_CHECKING, "checking"),
        ("Demo Rainy Day Savings", "savings"),
        ("Demo Credit Card", "credit_card"),
        ("Demo Brokerage", "brokerage"),
    ]:
        acct[kind] = api.call(
            "POST", "/api/local/accounts", {"name": name, "kind": kind}
        )["id"]

    print("Setting monthly budgets...")
    cats = {c["name"]: c["id"] for c in api.items("/api/local/categories")}
    budgets = {
        "Rent/Mortgage": 150000,
        "Utilities": 18000,
        "Groceries": 60000,
        "Transportation": 25000,
        "Insurance": 15000,
        "Healthcare": 10000,
        "Dining Out": 20000,
        "Entertainment": 10000,
        "Shopping": 15000,
        "Subscriptions": 4000,
        "Travel": 10000,
        "Emergency Fund": 30000,
        "Investments": 20000,
    }
    for name, cents in budgets.items():
        if name in cats:
            api.call(
                "PATCH", f"/api/local/categories/{cats[name]}", {"budget_cents": cents}
            )

    def tx(account, date, cents, description, category=None, kind="normal"):
        body = {
            "account_id": acct[account],
            "date": date.isoformat(),
            "amount_cents": cents,
            "description": description,
            "kind": kind,
        }
        if category:
            body["category_id"] = cats[category]
        return api.call("POST", "/api/local/transactions", body)["id"]

    start = months_back(today, 2)
    print("Adding opening balances...")
    tx("checking", start, 300000, "Opening balance", kind="adjustment")
    tx("savings", start, 500000, "Opening balance", kind="adjustment")

    print("Adding three months of everyday spending and paychecks...")
    for n in (2, 1, 0):
        first = months_back(today, n)

        def day(d, first=first):
            return first.replace(day=d)

        def happened(d):
            return d <= today

        for pay_day in (1, 15):
            if happened(day(pay_day)):
                deposit = tx(
                    "checking",
                    day(pay_day),
                    260000,
                    "DEMO EMPLOYER PAYROLL",
                    "Paycheck",
                )
                paycheck = api.call(
                    "POST",
                    "/api/local/paychecks",
                    {
                        "pay_date": day(pay_day).isoformat(),
                        "employer": "Demo Employer Inc.",
                        "account_id": acct["checking"],
                        "gross_cents": 340000,
                        "federal_tax_cents": 34000,
                        "state_tax_cents": 12000,
                        "social_security_cents": 21080,
                        "medicare_cents": 4930,
                        "retirement_cents": 7990,
                        "net_cents": 260000,
                    },
                )
                api.call(
                    "POST",
                    f"/api/local/paychecks/{paycheck['id']}/deposit",
                    {"transaction_id": deposit},
                )
        spending = [
            (1, "checking", -150000, "DEMO APARTMENTS RENT", "Rent/Mortgage"),
            (3, "credit_card", -1549, "DEMO STREAMING", "Subscriptions"),
            (5, "credit_card", -8734, "DEMO GROCERY MART", "Groceries"),
            (8, "checking", -14237, "DEMO POWER & WATER", "Utilities"),
            (9, "credit_card", -4512, "DEMO GAS STATION", "Transportation"),
            (12, "credit_card", -11865, "DEMO GROCERY MART", "Groceries"),
            (14, "credit_card", -3899, "DEMO TACO PLACE", "Dining Out"),
            (16, "checking", -12500, "DEMO AUTO INSURANCE", "Insurance"),
            (18, "credit_card", -6420, "DEMO OUTLET STORE", "Shopping"),
            (19, "credit_card", -9310, "DEMO GROCERY MART", "Groceries"),
            (21, "credit_card", -2600, "DEMO CINEMA", "Entertainment"),
            (24, "credit_card", -4188, "DEMO GAS STATION", "Transportation"),
            (26, "credit_card", -10276, "DEMO GROCERY MART", "Groceries"),
            (27, "credit_card", -5150, "DEMO BISTRO", "Dining Out"),
        ]
        for d, account, cents, description, category in spending:
            if category in EVERYDAY:
                cents = -(-cents * MONTH_PERCENT[n] // 100)  # whole cents
            if happened(day(d)):
                tx(account, day(d), cents, description, category)
        if happened(day(20)):
            tx(
                "credit_card",
                day(20),
                2399,
                "DEMO OUTLET STORE RETURN",
                "Shopping",
                kind="refund",
            )
            tx(
                "credit_card", day(20), -1875, "DEMO UNKNOWN SHOP"
            )  # left unsorted on purpose
        if happened(
            day(22)
        ):  # move money to savings: linking the two sides makes it a transfer
            out = tx("checking", day(22), -30000, "Transfer to savings")
            back = tx("savings", day(22), 30000, "Transfer from checking")
            api.call(
                "POST", f"/api/local/transactions/{out}/transfer", {"other_id": back}
            )

    year = today.year
    print("Adding demo donations...")
    for date, org, kind, cents in [
        (dt.date(year, 1, 20), "Demo Food Bank", "cash", 5000),
        (dt.date(year, 3, 14), "Demo Animal Shelter", "cash", 30000),
        (dt.date(year, 6, 2), "Demo Thrift Charity", "goods", 65000),
    ]:
        if date <= today:
            api.call(
                "POST",
                "/api/local/donations",
                {
                    "date": date.isoformat(),
                    "organization": org,
                    "kind": kind,
                    "amount_cents": cents,
                },
            )

    print("Adding demo stock purchases and sales...")
    brokerage = acct["brokerage"]
    for symbol, acquired_on, shares, cost in [
        ("DEMO", dt.date(year - 1, 1, 10), "10", 100000),
        ("FAKE", dt.date(year, 2, 1), "5", 40000),
    ]:
        api.call(
            "POST",
            "/api/local/stocks/lots",
            {
                "account_id": brokerage,
                "symbol": symbol,
                "acquired_on": acquired_on.isoformat(),
                "shares": shares,
                "cost_basis_cents": cost,
            },
        )
    for symbol, sold_on, shares, proceeds in [
        ("DEMO", dt.date(year, 3, 2), "4", 52000),  # long-term gain
        ("FAKE", dt.date(year, 2, 20), "2", 12000),  # short-term loss
    ]:
        if sold_on <= today:
            api.call(
                "POST",
                "/api/local/stocks/sales",
                {
                    "account_id": brokerage,
                    "symbol": symbol,
                    "sold_on": sold_on.isoformat(),
                    "shares": shares,
                    "proceeds_cents": proceeds,
                },
            )


if __name__ == "__main__":
    sys.exit(main())
