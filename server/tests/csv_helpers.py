"""Helpers for the bank-CSV import tests. Every file here is made up."""

CHECKING_CSV = (
    "Date,Description,Amount,Balance\r\n"
    '01/03/2026,FAKE GROCERY 123,"-$1,234.56",100.00\r\n'
    '01/04/2026,Fake Payroll,"$2,000.00",2100.00\r\n'
    "01/05/2026,Fake Coffee,(4.50),2095.50\r\n"
    "01/05/2026,Fake Coffee,(4.50),2091.00\r\n"
)


def url(account_id: int, action: str = "preview") -> str:
    base = f"/api/local/accounts/{account_id}/csv-import"
    return base if action == "commit" else f"{base}/{action}"


def send(client, account_id, body, action="preview", content_type="text/csv", **params):
    if isinstance(body, str):
        body = body.encode()
    headers = {"Content-Type": content_type}
    return client.post(url(account_id, action), content=body, params=params, headers=headers)


def ok(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()


def txns(client, account_id) -> list[dict]:
    items = client.get("/api/local/transactions", params={"account_id": account_id}).json()
    return sorted(items["items"], key=lambda t: t["id"])
