# Privacy statement

Budget Buddy keeps your money records on your own devices. We don't run a server for it. Nothing goes to us or to any cloud service of ours, and we can't see your data. There's no account and no sign-in.

## What Budget Buddy keeps

- Accounts, balances and transactions (what you spent and received), and budget categories
- Paychecks: employer, pay, taxes and deposits
- Receipts: photos, and the shop, total and note you type
- Donations to charities
- Stock and fund purchases, sales, dividends and holdings
- Tax deductions you enter, and the names of files you imported
- Phones and other computers you connected

## Where it's kept

- **Your computer:** in the data folder. By default that's `%LOCALAPPDATA%\BudgetBuddy`, unless you moved it. Receipt photos and old copies are in it too.
- **Your phone:** a short copy of this month's budget and any receipts waiting to go to your computer. Both are scrambled with a key that stays on the phone, and they're left out of phone backups.
- **Backup files:** wherever you save them. See Backups below.

## What's encrypted, and what isn't yet

These are scrambled with strong encryption (AES-256). The key is kept in your computer's password vault:

- Account numbers (last four digits), bank names and account notes
- Notes on transactions, paychecks, receipts and donations
- Employer names, charity names and shop names on receipts
- Deduction descriptions and the names of imported files
- Receipt photos
- Your Finnhub key, and the keys for your connected phones

These are **not** encrypted yet, because Budget Buddy needs to read them to search, sort and add up:

- Every amount and date
- Transaction descriptions and account names
- Gross and net pay on paychecks
- Company names on dividends and on stock trades from your bank file
- Category names and auto-sort rule text
- Stock symbols and lots

Encrypted names can still show up in descriptions and account names, so keep your data folder private. Encrypting more is planned, not built yet ([issue #28](https://github.com/Redsuperninja/budget-buddy/issues/28)). For the full picture, see [Keep your data safe](guide/keep-your-data-safe.md).

## The one optional outside connection: live stock prices

It's off until you turn it on. When it's on:

- **What's sent:** the symbols you hold, such as VTI, one at a time, and your own free Finnhub key. Nothing else: no amounts, accounts or names.
- **When:** only when you open the Investments page or click **Refresh prices**. Never in the background.
- **Who sees it:** Finnhub, the price service, sees those symbols tied to your Finnhub account. Like any website, it also sees your computer's internet connection.
- **Turning it off:** choose **Off**, or click **Remove my key and turn off**.

Your phone never contacts Finnhub. Only your computer does.

## No analytics, tracking or ads

Budget Buddy has no analytics, tracking or ads. It doesn't send usage statistics or crash reports anywhere. Its only outside request is the price check above.

## How phones and other computers connect

- Phones and computers connect only on your home network. Anything else is refused.
- A phone pairs with a one-time code that works for 10 minutes. After that, its syncs are scrambled, and each message works only once.
- Other computers, and phone browsers, that you join with a one-time code connect over plain HTTP on your home network. Budget Buddy doesn't scramble that traffic, so use them only on Wi-Fi you trust.
- To remove a phone, go to **Devices** and find **Connected phones**, then click **Remove**.

## Backups

- Go to **Devices → Backups** and click **Download a backup**. Your browser saves one file, usually to your Downloads folder.
- The file holds all your data and receipt photos. It's scrambled as a whole. Only your computer, or your recovery phrase, can open it.
- The file holds no key. It shows only its size, its date and which computer's key made it.
- A restore checks the whole file first. Your current data is moved to a `before-restore` folder, and Budget Buddy never deletes it for you.

For steps, see [Back up and restore your data](guide/back-up-and-restore.md).

## Old copies

When Budget Buddy updates its database, it first saves a copy named `budget.db.bak-` and a number, in the data folder. Every copy holds your amounts and descriptions in readable form, like the main database. Copies made before the names were encrypted also hold those names in plain text. See [Old backup copies](guide/keep-your-data-safe.md#old-backup-copies).

## Deleting everything

Do these steps in order.

1. **Close Budget Buddy.** If you use the desktop app, right-click its tray icon and choose **Quit**.
2. **Remove your phones.** On the dashboard, go to **Devices**, find **Connected phones** and click **Remove** for each one. Then uninstall the phone app, and clear its storage first if you can. In your phone's web browser, clear the data for Budget Buddy's address.
3. **Delete the data folder.** In File Explorer's address bar, type `%LOCALAPPDATA%\BudgetBuddy` and press Enter. Select the folder and press Delete. This removes your database, receipt photos, old copies and `before-restore` folders.
4. **Delete your backup files.** Look in Downloads, on any USB drives and in any cloud folders for files ending in `.bbbackup`, and delete them.
5. **Remove the password-vault entry.** Open Credential Manager, choose **Windows Credentials**, find the entry whose name starts with `budget-buddy`, and click **Remove**. Do this after step 3.
6. **Uninstall.** Open Windows **Settings**, then **Apps**, then **Budget Buddy**, and choose **Uninstall**.
7. **Empty the Recycle Bin.** Deleted files stay there until you empty it.

Once steps 3 and 5 are done, your data can't be recovered, even with your recovery phrase, unless you kept a backup and its phrase.

## Something went wrong?

- **You can't find the data folder.** Type `%LOCALAPPDATA%\BudgetBuddy` into File Explorer's address bar. If you moved the folder, use the one you chose. See [Move your data folder](guide/move-your-data-folder.md).
- **Credential Manager has no Budget Buddy entry.** Budget Buddy has no key saved on this Windows account, or it's already gone. There's nothing to remove.
- **Files come back after you delete them.** Empty the Recycle Bin, then check Downloads and your USB drives for backup files.

For developers, the technical details are in [Security and privacy](dev/architecture/security.md).
