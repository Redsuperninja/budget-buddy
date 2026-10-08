# Settings (environment variables)

The only place these are listed. All are optional; the Home Base reads them at startup (`server/app/config.py`).
User guides never name them; they say "ask whoever set up Budget Buddy" and link here.

| Variable | Default | Meaning |
| --- | --- | --- |
| `BUDGET_BUDDY_DATA_DIR` | `%LOCALAPPDATA%\BudgetBuddy` (Windows), `~/.local/share/budget-buddy` (others) | Where the data is kept. Never inside this repo. |
| `BUDGET_BUDDY_HOST` | `127.0.0.1` | Leave unset. The Home Base listens on this computer only and opens a home-network listener by itself while pairing or once a phone is paired ([architecture/pairing.md](architecture/pairing.md)). `127.0.0.1` means phones can never connect. Any other address becomes the main listener (not recommended). |
| `BUDGET_BUDDY_LAN_IP` | detected | This computer's home-network address (such as `192.168.1.20`), put in the pairing QR and used for the phone listener. Set it if detection picks the wrong one. Must be a private address. |
| `BUDGET_BUDDY_SERVER_NAME` | `Home Base` | The name the phone shows for this computer (50 characters at most). |
| `BUDGET_BUDDY_PORT` | `8765` | Port to listen on. The test server uses `8766`. |
| `BUDGET_BUDDY_DASHBOARD_DIR` | `<repo>/dashboard` | Folder with the web dashboard files. If it isn't there, the server runs API-only ([architecture/dashboard.md](architecture/dashboard.md)). |
| `BUDGET_BUDDY_DEV_MODE` | `false` | `true` turns on the API explorer at `/docs`. |
| `BUDGET_BUDDY_KEY_STORE` | `keyring` | Where the encryption key is kept. `memory` is for automated tests only and also needs `BUDGET_BUDDY_INSECURE_TEST_KEYSTORE=1` ([testing.md](testing.md)). |
| `BUDGET_BUDDY_INSECURE_TEST_KEYSTORE` | unset | Test-only switch that allows the memory key store. Never use it for real data. |

## Moving your data folder

If the Home Base warns that the data folder is inside a code project or a cloud-synced folder (OneDrive,
Dropbox, iCloud, Google Drive, Box, pCloud, Nextcloud; on a Mac also `Desktop` and `Documents` when iCloud syncs
them), close the Home Base, move the whole folder somewhere unsynced, set `BUDGET_BUDDY_DATA_DIR` to its full
path, and start again. The key stays in the OS password vault, so it still works after the move.
