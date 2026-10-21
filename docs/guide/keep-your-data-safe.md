# Keep your data safe

Your Budget Buddy data stays on your computer only. Nothing goes to the cloud. Learn how to protect it with encryption and backups.

## What's encrypted

Account numbers, bank names, notes, employer names, charity names, shop names on receipts, and receipt photos are encrypted. The encryption key is kept in your computer's password vault (Windows Credential Manager, macOS Keychain, or Linux Secret Service), never in the data folder.

**Not everything is encrypted yet.** Amounts, dates, transaction descriptions, and account names are not encrypted, so anyone with a copy of the data folder can still read your spending, pay, and giving history. Keep the data folder out of cloud-synced folders (OneDrive, Dropbox, iCloud) and protect your Windows account with a password.

Encrypted on your computer:
- Account numbers and bank names
- Transaction notes
- Receipt photos and text
- Donation notes and charity names
- Employer names on paychecks
- Shop names on receipts
- Account notes and paycheck notes
- Deduction descriptions and the names of imported files
- Your Finnhub key, and the keys for your connected phones

**Not encrypted (but you need them for Budget Buddy to work):**
- Every amount and date
- Transaction description
- Pay amounts on paychecks
- Account names
- Company names on dividends and bank-made stock trades
- Category names and auto-sort rule text
- Stock symbols and lots

The encrypted names can still show up in the unencrypted transaction descriptions and account names (for example a payment described as "FOOD BANK"), so treat the data folder as private anyway.

## Your recovery phrase

The encryption key is created the first time Budget Buddy starts. **Save your recovery phrase right away**, before anything goes wrong.

If your computer's password vault is ever lost (for example after reinstalling Windows or moving to a new computer), you can put the key back using your recovery phrase. Without the phrase, a lost key means the encrypted data can't be recovered.

To see your recovery phrase:
1. On the Budget Buddy computer, open the dashboard and go to **Devices → Backups**.
2. Make sure nobody else can see your screen, then click **Show my recovery phrase** and confirm.
3. Write the words on paper, or keep them in a password manager. Don't save a photo or a file on the computer.
4. Click **Hide it**.

The phrase also unlocks your backups: see [Back up and restore your data](back-up-and-restore.md).

## Old backup copies

Each time Budget Buddy updates its database, it first saves a copy of your data folder's database: `budget.db.bak-0001`, `budget.db.bak-0002`, and so on. Every copy holds your amounts and transaction descriptions as plain text, just like the main database. Any copy made before the update that encrypted bank, employer, charity and shop names (copies numbered 0027 or lower) also holds those names as plain text, and older copies also hold account numbers and notes that way. You can delete them once Budget Buddy is working well and you've saved your recovery phrase.

To delete them safely:
1. Make sure Budget Buddy is running, so it makes a fresh backup if needed
2. Look in your data folder for files named `budget.db.bak-*`
3. Delete the old `.bak-*` copies (keep the current `.db` file)

## Something went wrong?

**"Budget Buddy can't find the right key in this computer's password vault"**

The key isn't in this computer's password vault (or it's a different one), so there's no phrase to show. If you
saved your phrase before, ask whoever set up Budget Buddy to put it back.

**"Budget Buddy couldn't use this computer's password vault"**

Budget Buddy keeps its key only in the computer's own password vault. On Linux, install and unlock GNOME
Keyring or KWallet. A keyring that saves passwords in a plain file (like `keyrings.alt`) isn't used, because the
key would then sit in a file anyone with the computer could read.

**"We found an old backup copy of your data folder that isn't encrypted"**

The old copy was made before encryption existed. You can delete it safely once you've saved your recovery phrase and verified that Budget Buddy is working well.
