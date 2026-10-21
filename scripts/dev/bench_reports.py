"""Time the report endpoints on a made-up ledger. Run from server/:
.venv/Scripts/python ../scripts/dev/bench_reports.py [count]. Fake data in a temp folder only."""

import datetime as dt
import os
import sys
import tempfile
import time

os.environ["BUDGET_BUDDY_DATA_DIR"] = tempfile.mkdtemp(prefix="bb-bench-")
os.environ["BUDGET_BUDDY_KEY_STORE"] = "memory"
os.environ["BUDGET_BUDDY_INSECURE_TEST_KEYSTORE"] = "1"  # fake data only

from app.main import create_app  # noqa: E402
from app.models import Transaction  # noqa: E402
from app.models.enums import TransactionKind, TransactionSource  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000
SWEEP = "FAKE DEPOSIT SWEEP INTRA-DAY"
TRADE = "FAKECO UNSOLICITED WE ARE ACTING AS PRINCIPAL"

app = create_app()
base = "http://127.0.0.1:8765"
client = TestClient(
    app,
    base_url=base,
    client=("127.0.0.1", 5),
    headers={"Origin": base, "X-CSRF-Token": app.state.csrf_token},
)
ids = [
    client.post("/api/local/accounts", json={"name": f"Fake {k}", "kind": k}).json()["id"]
    for k in ("checking", "brokerage")
]
start = dt.date.today() - dt.timedelta(days=700)
with Session(app.state.engine) as s:
    for i in range(COUNT):
        s.add(
            Transaction(
                account_id=ids[i % 2],
                date=start + dt.timedelta(days=i % 700),
                amount_cents=(-1) ** i * (100 + i % 997),
                notes=f"fake note {i}",
                source=TransactionSource.MANUAL,
                kind=TransactionKind.NORMAL,
                description=SWEEP if i % 20 == 1 else TRADE if i % 200 == 3 else f"FAKE ITEM {i}",
            )
        )
    s.commit()
for name, method, url in [
    ("trend", "get", f"/api/local/summary/trend?end={dt.date.today():%Y-%m}"),
    ("sweeps", "get", "/api/local/stocks/sweeps"),
    ("bank-trades/find", "post", "/api/local/stocks/bank-trades/find"),
    ("match-transfers", "post", "/api/local/transactions/match-transfers"),
    ("transactions", "get", "/api/local/transactions"),
]:
    t = time.perf_counter()
    r = getattr(client, method)(url)
    print(f"{name}: {(time.perf_counter() - t) * 1000:.0f} ms (HTTP {r.status_code})")
