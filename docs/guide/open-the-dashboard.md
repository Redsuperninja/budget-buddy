# Open the dashboard

The Budget Buddy dashboard is a web page that shows your budget, accounts, and spending. It runs on your Budget
Buddy computer; a phone or another computer at home can open it too once you connect it with a one-time code.
If you installed the [desktop app](desktop-app.md), it shows the same pages in its own window.

## Open it in your browser

1. Start Budget Buddy on your computer (the Home Base server)
2. Open a web browser (Chrome, Edge, Firefox, Safari — any browser works)
3. Go to http://127.0.0.1:8765/ or type that address in the address bar
4. You'll see the Budget Buddy dashboard with five buttons at the top: **Home**, **Money**, **Budget**, **Taxes** and
   **Devices**, and **Settings** at the top right

The first time, **Home** shows a **Get started** list: add your accounts, bring in what you spent, set monthly
budgets, and (if you like) use it on your phone. Each step links to the page that does it, and the list goes away
once the first three are done.

**Your data stays on this computer.** The dashboard works on this computer, and on other computers at home only
after you connect them with a one-time code ([use Budget Buddy on another computer](use-on-another-computer.md)).

## Charts

The **Home** page shows your month at a glance:

- **Four tiles:** money in (what everything else is measured against), what you spent (with a bar for how much of
  your spending budget that is), what you saved (and what share of your income), and what's left over.
- **Needs your attention:** transactions with no category, pay deposits to fill in, and investment positions
  that don't match your recorded trades. Click one to go there. "All caught up" means nothing's waiting.
- **Where your income went:** one bar the length of your income, split into needs, wants and savings, with what's
  left over in gray. If you spent and saved more than came in, a line marks where your income ran out.
- **What you have and owe:** your net worth, and a bar for each account: money you have to the right, money you
  owe (credit cards, loans) to the left.

It also has these charts:

- **Needs, wants and savings** and **Budget and actual by category:** a bar for what you've spent this month,
  and a short upright line where your budget is. If the bar goes past the line, you're over budget (the amount
  on the right also says "over").
- **The last 12 months:** lines for money in, spending and saving. Point at a month to see its exact numbers.

Click **Show as table** on any chart to see the same numbers as a list.

## Simple view or All tools

Budget Buddy starts in the **simple view**: the pages and buttons most people need. When you want more control,
click **Settings** at the top right and set **View** to **All tools**. That adds:

- the **Import history** and **Auto-sort** pages (under **Money**)
- on **Transactions**: **Find transfers**, **Hide dividends and sweeps**, **Hide balance adjustments**, the
  **Mark as gift** and **Stock trade** buttons, and the transaction **Type** (refund or balance adjustment)
- on **Investments**: importing your broker's positions file, and the live prices settings

Nothing is lost in the simple view: your rules, imports and settings keep working, they're just out of the way.
Set **View** back to **Simple** any time. The choice is remembered in this browser.

## Light or dark

Budget Buddy follows your computer's light or dark setting. To pick one yourself, open **Settings** at the top
right and set **Colors** to **Match my computer**, **Light** or **Dark**. Your choice is remembered in this browser.

## Finding your way around

The buttons at the top each open a section. **Money**, **Budget** and **Taxes** have a few pages each: when
you open one, a row of tabs appears just below the buttons. Click a tab to switch pages.

- **Home:** your monthly budget: money in, money spent, money saved, how much of each budget you've used, what
  share of your income went to needs, wants and savings, and your account balances
- **Money**
  - **Transactions:** money coming in and going out; add more; sort a payment into charity
  - **Accounts:** your bank and savings accounts; match a balance to your bank
  - **Investments:** what you hold in each account and what it's worth; retirement and HSA contributions
  - **Import files:** import a CSV from your bank, or your broker's activity file
  - **Receipts:** receipt photos sent from your phone
  - **Import history** (All tools): every file you imported; undo one
  - **Auto-sort** (All tools): rules that put transactions in the right category for you
- **Budget**
  - **Categories:** budget categories and monthly budgets, as amounts or percentages of income
  - **Suggested budget:** a 50/30/20 plan from your last three months
- **Taxes** (estimates only, not tax advice)
  - **Tax summary:** other deductions and one page per tax year to download or print
  - **Donations:** gifts to charity and the proof to keep
  - **Paychecks:** pay stubs and year-to-date totals
  - **Stocks:** purchases and sales; gains and losses
- **Devices** (only on the Budget Buddy computer)
  - **Connect phone:** pair your phone so it can see your budget
  - **Other devices:** open Budget Buddy in the web browser of another computer or a phone at home

Receipts are added from the phone app.

## Something went wrong?

**"This only works on the computer where Budget Buddy is running"** or **"This computer isn't connected to
Budget Buddy yet"**

Open http://127.0.0.1:8765/ in a browser on the computer where Budget Buddy is running. To use another computer,
connect it first ([use Budget Buddy on another computer](use-on-another-computer.md)). It never works over the
internet.

**The page won't load**

1. Make sure Budget Buddy (the Home Base server) is running
2. Try typing the address again: http://127.0.0.1:8765/
3. If it still doesn't work, close your browser and try a different one
4. Restart Budget Buddy
