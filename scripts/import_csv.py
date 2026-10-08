"""Preview a bank CSV file, then import it into an account on the TEST Home Base.

Run it via scripts/import-csv.ps1. Shows what Budget Buddy understood (columns, dates, amounts, and
any problem rows) and asks before saving anything.
"""

import argparse
import sys
import urllib.parse
from pathlib import Path

from _local_api import ApiError, LocalApi, NotRunning
from _testguard import refuse_unless_test_server


def call(api: LocalApi, method: str, path: str, body: bytes | None = None):
    """One request; a refusal or a missing Home Base ends the script with a plain message."""
    try:
        return api.call(method, path, body=body, content_type="text/csv", timeout=30)
    except NotRunning:
        raise SystemExit(
            "The test Home Base isn't running. Start scripts\\start-test-server.ps1 first."
        ) from None
    except ApiError as exc:
        raise SystemExit(f"Budget Buddy said: {exc}") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument(
        "--account", default="Demo Everyday Checking", help="account name"
    )
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument(
        "--flip-sign", action="store_true", help="for credit card files"
    )
    parser.add_argument(
        "--skip-invalid",
        action="store_true",
        help="import the rest if some rows are bad",
    )
    args = parser.parse_args()
    reason = refuse_unless_test_server(args.port)
    if reason:
        print(reason)
        return 2
    if not args.file.is_file():
        print(f"Couldn't find the file {args.file}.")
        return 1
    api = LocalApi(f"http://127.0.0.1:{args.port}")

    accounts = call(api, "GET", "/api/local/accounts")
    accounts = accounts["items"] if isinstance(accounts, dict) else accounts
    match = [a for a in accounts if a["name"].lower() == args.account.lower()]
    if not match:
        names = ", ".join(a["name"] for a in accounts) or "none yet"
        print(f'No account called "{args.account}". Your accounts: {names}')
        return 1
    account_id = match[0]["id"]

    choices = {}
    if args.flip_sign:
        choices["flip_sign"] = "true"
    query = urllib.parse.urlencode(choices)
    commit_query = urllib.parse.urlencode(
        choices | ({"skip_invalid_rows": "true"} if args.skip_invalid else {})
    )
    path = f"/api/local/accounts/{account_id}/csv-import"
    data = args.file.read_bytes()
    preview = call(api, "POST", f"{path}/preview?{query}", data)

    mapping = preview.get("mapping") or {}
    print(
        f'Reading "{args.file.name}" into "{match[0]["name"]}". Dates look like {mapping.get("date_format")}.'
    )
    if preview.get("message"):
        print(preview["message"])
    rows = preview.get("rows") or []
    print(f"\n{'Row':>4}  {'Date':10}  {'Amount':>11}  {'Status':10}  Description")
    for row in rows[:25]:
        cents = row.get("amount_cents")
        amount = (
            ""
            if cents is None
            else f"{'-' if cents < 0 else ''}${abs(cents) / 100:,.2f}"
        )
        status = row.get("status") or ""
        line = f"{row['row_number']:>4}  {row.get('date') or '?':10}  {amount:>11}  {status:10}  {row.get('description') or ''}"
        print(line + (f"   <- {row['problem']}" if row.get("problem") else ""))
    if len(rows) > 25:
        print(f"   ...and {len(rows) - 25} more rows")

    if any(r.get("status") == "invalid" for r in rows) and not args.skip_invalid:
        print(
            "\nSome rows have problems. Fix the file, or run again with -SkipInvalid to import the rest."
        )
        return 1
    if input("\nImport these rows? Type y and press Enter: ").strip().lower() != "y":
        print("Nothing was imported.")
        return 0
    result = call(api, "POST", f"{path}?{commit_query}", data)
    print(
        f"Imported {result['imported']} rows. Skipped {result['skipped_duplicates']} already there"
        f" and {result['skipped_invalid']} with problems."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
