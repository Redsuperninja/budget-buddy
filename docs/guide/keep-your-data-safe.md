# Keep your data safe

Your Budget Buddy data stays on your computer only. Nothing goes to the cloud. Learn how to protect it with encryption and backups.

## What's encrypted

Your whole database file is encrypted, so your amounts, dates, descriptions, account names and categories can't be read without your key. The most private details (account numbers, bank, employer, charity and shop names, notes) are also scrambled inside it, and receipt photos are scrambled as separate files. The encryption key is kept in your computer's password vault (Windows Credential Manager, macOS Keychain, or Linux Secret Service), never in the data folder.

When you update from an older version, Budget Buddy moves your existing data into the encrypted file the first time it starts. If anything goes wrong it stops and leaves your data as it was.

Keep the data folder out of cloud-synced folders (OneDrive, Dropbox, iCloud) and protect your Windows account with a password: old copies, and anything a sync service already saved, are not covered.

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

Each time Budget Buddy updates its database, it first saves a copy of your data folder's database: `budget.db.bak-0001`, `budget.db.bak-0002`, and so on. Copies made by this version are encrypted like the main database. Copies made by older versions are not: they hold your amounts and transaction descriptions as plain text, and the oldest also hold names, account numbers and notes that way. When Budget Buddy first encrypts your database it lists the old copies in its log. You can delete them once Budget Buddy is working well and you've saved your recovery phrase.

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
