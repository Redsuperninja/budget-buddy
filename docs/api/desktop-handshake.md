# Desktop handshake: is the Home Base on the port really Budget Buddy?

The rules the desktop app (`desktop/budget_buddy_desktop/genuine.py`) and the Home Base
(`server/app/instance_proof.py`, `server/app/config.py`) must agree on. Parts never import each other's code
([architecture](../dev/architecture/README.md#the-parts-and-their-boundaries)), so each side keeps its own copy, and
**both test suites read the example below**: change a rule here and on both sides in the same branch. Background:
[ADR-0008](../adr/0008-desktop-app.md), [desktop.md](../dev/architecture/desktop.md).

## Rules

1. **Data folder.** `BUDGET_BUDDY_DATA_DIR` if set; otherwise `%LOCALAPPDATA%\BudgetBuddy` on Windows (or
   `~\AppData\Local\BudgetBuddy` without `LOCALAPPDATA`) and `~/.local/share/budget-buddy` elsewhere.
2. **Running file.** While it runs, the Home Base keeps `home-base-running.json` in the data folder:
   `{"port": <int>, "pid": <int>, "key": "<64 hex characters>"}`, readable only by this user. It's removed on a
   clean stop; the desktop ignores it when `port` differs or `pid` isn't running.
3. **Challenge.** The desktop sends `GET /api/local/instance/proof?nonce=<32 to 128 lowercase hex>` (this computer
   only) and gets `{"proof": "<hex>"}`, the HMAC-SHA256 of the nonce's ASCII text under the key's bytes.

## Example

Both test suites check these values.

```json
{
  "running_file": "home-base-running.json",
  "proof_path": "/api/local/instance/proof",
  "data_folder": {
    "override_variable": "BUDGET_BUDDY_DATA_DIR",
    "windows": ["LOCALAPPDATA", "BudgetBuddy"],
    "elsewhere": [".local", "share", "budget-buddy"]
  },
  "key": "1111111111111111111111111111111111111111111111111111111111111111",
  "nonce": "0123456789abcdef0123456789abcdef",
  "proof": "9012470a347cda80212ab0ffead88c1c5071ae2be3e242b589eaa5eb31c735bb"
}
```
