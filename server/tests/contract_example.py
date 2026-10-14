"""The example snapshot published in the sync contract (docs/api/sync-contract/05-snapshot.md §5.2).

The phone's tests read the same block (mobile/src/sync/__tests__/snapshot.test.ts), so the contract,
the server and the phone are all checked against one copy of the example.
"""

import json
import re
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "api" / "sync-contract" / "05-snapshot.md"


def contract_example() -> dict:
    blocks = re.findall(r"```json\n(.*?)```", DOC.read_text(encoding="utf-8"), re.S)
    assert len(blocks) == 1, f"expected one JSON example in {DOC.name}, found {len(blocks)}"
    return json.loads(blocks[0])


def shape(value):
    """Keys and kinds of value, not the values: lists by their first item, null as None."""
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return None if value is None else type(value).__name__
