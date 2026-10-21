# Budget Buddy

Budget Buddy is a private budgeting and US federal tax prep helper. It runs on your own Windows computer. Your
records stay there, encrypted. There is no cloud, no account and no bank password to give anyone. A phone app is
optional.

![Budget Buddy's Home page: money in, spent, saved and left over (made-up demo data)](docs/showcase/images/home.png)

> Budget Buddy organizes your records and estimates numbers to help you prepare.
> It is not tax advice. Check important decisions with a tax professional.

**New here?** Read [What Budget Buddy is (plain English)](docs/showcase/overview.md).

## Who it's for

- People who want to track spending, savings and budgets without handing their money records to a website.
- People who want their federal tax details (donations, stock sales, paychecks, medical bills and more) gathered in
  one place before tax time.

## What you need

- A Windows 10 or Windows 11 computer. Installing from the download needs no admin rights and no Python.
- A Mac or Linux computer can run Budget Buddy too, but only from source. See the
  [start guide](docs/guide/start-budget-buddy.md) (it needs Python 3.12 or newer).
- Optional: a phone on your home Wi-Fi, to use Budget Buddy in its web browser.

## What Budget Buddy does not do

- **No state taxes.** It only covers US federal taxes.
- **No filing.** It doesn't send anything to the IRS or any tax program. You file your own return.
- **Not tax advice.** It shows your numbers and estimates. It doesn't decide what you owe.
- **No bank login.** It reads the files your bank lets you download (CSV). It doesn't log in to your bank. Bank
  connections are not in this version, and would only ever use a key you add yourself.
- **No cloud.** Your data is not uploaded anywhere. The one outside call is optional live stock prices (see
  [privacy](docs/PRIVACY.md)).

## What it does

| Area | Features |
| --- | --- |
| Getting started | A **Get started** checklist on Home; a simple view, with **All tools** one switch away in **Settings** |
| Money in | Paychecks (gross, taxes withheld, net, 401k/HSA), started for you from pay deposits in your bank file |
| Accounts | Checking, savings, cards, loans, brokerage, retirement and HSA: import bank CSV files or enter by hand |
| Spending | Search and filter by category; auto-sorted transactions; transfers between your accounts linked for you; receipt photos from your phone |
| Budget | A suggested 50/30/20 budget from your real income and spending, monthly targets vs. actual, charts |
| Investments | Holdings by account, at live prices (optional) or prices you enter; broker files; 401(k), IRA and HSA limits |
| Taxes | Donations, stock gains (short and long-term, possible wash sales), dividends, other deductions, and a yearly summary to download or print |
| Devices | Phones and other computers at home join with a one-time code |

## Download and first start

1. Go to the project's [Releases page](https://github.com/Redsuperninja/budget-buddy/releases) and download
   `Budget-Buddy-<version>-Windows.zip`.
2. Right-click the zip, choose **Extract All...**, then double-click **Install Budget Buddy**.
3. Open **Budget Buddy** from the Start menu.

Step-by-step help, with pictures: [Download and install Budget Buddy](docs/guide/install.md). After that, Budget
Buddy opens on Home with a **Get started** list. The [user guide](docs/guide/README.md) covers everything else.

Windows may say it protected your PC, because this early version isn't signed yet. The install page shows how to
continue, and only do this for a copy from the Releases page above.

Write down the recovery phrase Budget Buddy shows you, and keep it somewhere safe. Without it, a lost computer
means lost data. See [keep your data safe](docs/guide/keep-your-data-safe.md).

## Privacy and security

- Your records are stored on your computer, encrypted. Nothing is sent to us or to a cloud service.
- Read [docs/PRIVACY.md](docs/PRIVACY.md) for what is kept, where, and how to delete everything.
- Read [SECURITY.md](SECURITY.md) for how to report a problem privately.

## Status

Early release (0.1). The Windows download is ready to try. Phones use their web browser for now. A phone app is
being tested. See the [roadmap](docs/ROADMAP.md) for what's next.

## License

MIT, see [LICENSE](LICENSE).

## For developers

- [Contributing](CONTRIBUTING.md): how to set up, run the tests and send a change.
- [All the docs](docs/README.md) and [how it's built](docs/dev/README.md).
- [Making a release](docs/dev/release.md).
- [Trying it out with made-up data](docs/testing/README.md).

## Built with Claude

The code in Budget Buddy is written with [Claude Code](https://claude.com/claude-code), Anthropic's AI coding
assistant. The owner decides what gets built and reviews and approves each change before it's merged. See
[how the project is managed](docs/dev/workflow.md).
