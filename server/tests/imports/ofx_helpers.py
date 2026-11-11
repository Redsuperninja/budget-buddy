"""Made-up OFX files for the reader tests (no real bank, account or person)."""

SGML_HEADER = (
    "OFXHEADER:100\r\nDATA:OFXSGML\r\nVERSION:102\r\nSECURITY:NONE\r\nENCODING:USASCII\r\n"
    "CHARSET:1252\r\nCOMPRESSION:NONE\r\nOLDFILEUID:NONE\r\nNEWFILEUID:NONE\r\n\r\n"
)


def transaction(
    fitid="FAKE001",
    amount="-12.50",
    date="20260105120000.000[-5:EST]",
    name="FAKE GROCERY",
    memo="",
):
    memo_line = f"<MEMO>{memo}\r\n" if memo else ""
    return (
        f"<STMTTRN>\r\n<TRNTYPE>DEBIT\r\n<DTPOSTED>{date}\r\n<TRNAMT>{amount}\r\n"
        f"<FITID>{fitid}\r\n<NAME>{name}\r\n{memo_line}</STMTTRN>\r\n"
    )


def checking(transactions=None, acct="000123456789", balance="1234.56", cur="USD"):
    items = "".join(
        transactions
        if transactions is not None
        else [transaction(), transaction("FAKE002", "2000.00", name="FAKE PAYROLL")]
    )
    return (
        "<OFX>\r\n<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20260110</SONRS></SIGNONMSGSRSV1>\r\n"
        f"<BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STMTRS><CURDEF>{cur}\r\n"
        f"<BANKACCTFROM><BANKID>999999999<ACCTID>{acct}<ACCTTYPE>CHECKING</BANKACCTFROM>\r\n"
        f"<BANKTRANLIST><DTSTART>20260101<DTEND>20260110\r\n{items}</BANKTRANLIST>\r\n"
        f"<LEDGERBAL><BALAMT>{balance}<DTASOF>20260110120000</LEDGERBAL>\r\n"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\r\n"
    )


def card_xml(amount="-30.00"):
    return (
        '<?xml version="1.0" encoding="UTF-8"?><?OFX OFXHEADER="200" VERSION="220"?>'
        "<OFX><CREDITCARDMSGSRSV1><CCSTMTTRNRS><CCSTMTRS><CURDEF>USD</CURDEF>"
        "<CCACCTFROM><ACCTID>4111000011112222</ACCTID></CCACCTFROM><BANKTRANLIST>"
        f"<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260105</DTPOSTED><TRNAMT>{amount}</TRNAMT>"
        "<FITID>CARD1</FITID><NAME>FAKE &amp; SONS</NAME></STMTTRN></BANKTRANLIST>"
        "<LEDGERBAL><BALAMT>-30.00</BALAMT><DTASOF>20260106</DTASOF></LEDGERBAL>"
        "</CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1></OFX>"
    )


def sgml(body: str) -> bytes:
    return (SGML_HEADER + body).encode("cp1252")


def card_many(lines, acct="4111000011112222"):
    """A card file. ``lines``: (fitid, trntype, amount, name) tuples."""
    items = "".join(
        f"<STMTTRN><TRNTYPE>{kind}</TRNTYPE><DTPOSTED>20260105</DTPOSTED>"
        f"<TRNAMT>{amount}</TRNAMT><FITID>{fitid}</FITID><NAME>{name}</NAME></STMTTRN>"
        for fitid, kind, amount, name in lines
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><OFX><CREDITCARDMSGSRSV1><CCSTMTTRNRS><CCSTMTRS>'
        f"<CURDEF>USD</CURDEF><CCACCTFROM><ACCTID>{acct}</ACCTID></CCACCTFROM>"
        f"<BANKTRANLIST>{items}</BANKTRANLIST></CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1></OFX>"
    )


def join_statements(*files: str) -> bytes:
    """Several ``checking`` files' accounts in one file (the first file's wrapper is kept)."""
    first, *rest = files
    inner = "".join(f[f.index("<BANKMSGSRSV1>") + 14 : f.index("</BANKMSGSRSV1>")] for f in rest)
    return sgml(first.replace("</BANKMSGSRSV1>", inner + "</BANKMSGSRSV1>"))


def url(account_id, action=""):
    base = f"/api/local/accounts/{account_id}/ofx-import"
    return base if action == "commit" else f"{base}/{action}"


def send(client, account_id, body, action="preview", content_type="application/x-ofx", **params):
    if isinstance(body, str):
        body = body.encode()
    return client.post(
        url(account_id, action), content=body, params=params, headers={"Content-Type": content_type}
    )


def ok(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()


def txns(client, account_id) -> list[dict]:
    items = client.get("/api/local/transactions", params={"account_id": account_id}).json()
    return sorted(items["items"], key=lambda t: t["id"])
