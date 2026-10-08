# Keep your data safe

Your Budget Buddy data stays on your computer only. Nothing goes to the cloud. Learn how to protect it with encryption and backups.

## What's encrypted

Account numbers, notes, and receipt photos are encrypted. The encryption key is kept in your computer's password vault (Windows Credential Manager, macOS Keychain, or Linux Secret Service), never in the data folder.

**Not everything is encrypted yet.** Amounts, dates, descriptions, shop names, employer names, and charity names are not encrypted, so anyone with a copy of the data folder can still read your spending, pay, and giving history. Keep the data folder out of cloud-synced folders (OneDrive, Dropbox, iCloud) and protect your Windows account with a password.

Encrypted on your computer:
- Account numbers
- Transaction notes
- Receipt photos and text
- Donation notes

**Not encrypted (but you need them for Budget Buddy to work):**
- Every amount and date
- Transaction description
- Shop names on receipts
- Employer names and pay details on paychecks
- Account names and bank names
- Charity names on donations
- Stock symbols and lots

## Your recovery phrase

The encryption key is created the first time Budget Buddy starts. **Save your recovery phrase right away**, before anything goes wrong.

If your computer's password vault is ever lost (for example after reinstalling Windows or moving to a new computer), you can put the key back using your recovery phrase. Without the phrase, a lost key means the encrypted data can't be recovered.

To save your recovery phrase, ask whoever set up Budget Buddy how to get it — it's kept in your password vault, not written to the computer.

## Old backup copies

Before Budget Buddy added encryption, it made backup copies of your data folder: `budget.db.bak-0001`, `budget.db.bak-0002`, and so on. These old copies are not encrypted and were made before sensitive data was protected. You can delete them once Budget Buddy is working well and you've saved your recovery phrase.

To delete them safely:
1. Make sure Budget Buddy is running, so it makes a fresh backup if needed
2. Look in your data folder for files named `budget.db.bak-*`
3. Delete the old `.bak-*` copies (keep the current `.db` file)

## Something went wrong?

**"We found an old backup copy of your data folder that isn't encrypted"**

The old copy was made before encryption existed. You can delete it safely once you've saved your recovery phrase and verified that Budget Buddy is working well.
