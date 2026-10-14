Part of the [Sync API contract, v1](../sync-contract.md). Conventions and key names are in §1 there.

## 5. Snapshot schema

### 5.1 TypeScript

```ts
type Cents = number;       // integer
type IsoDate = string;     // "YYYY-MM-DD"
type IsoDateTime = string; // "2026-10-02T18:30:00Z"

export interface Snapshot {
  contract: 1;
  server_id: string;
  generated_at: IsoDateTime;
  currency: string;               // ISO 4217, e.g. "USD"
  period: {
    month: string;                // "2026-10"
    start: IsoDate;               // first day of month
    end: IsoDate;                 // last day of month
    days_elapsed: number;         // including today
    days_in_month: number;
  };
  income: {
    expected_cents: Cents;        // the larger of received so far and this month's paycheck take-home
    received_cents: Cents;        // take-home income received so far this month, >= 0
    last_paycheck: { pay_date: IsoDate; net_cents: Cents } | null;
  };
  budget: {
    target_cents: Cents;          // sum of group targets
    actual_cents: Cents;          // sum of group actuals
    groups: BudgetGroup[];        // always needs, wants, savings in that order
    unassigned?: { in_cents: Cents; out_cents: Cents; count: number }; // all >= 0
  };
  transactions: SnapshotTransaction[];
  accounts: SnapshotAccount[];
  tax: TaxSummary;
  settings: SyncSettings;
}

export interface BudgetGroup {
  group: 'needs' | 'wants' | 'savings';
  name: string;                   // display name, e.g. "Needs"
  target_cents: Cents;
  actual_cents: Cents;            // spent (needs/wants) or saved (savings) this month, >= 0 normally
  categories: BudgetCategory[];
}

export interface BudgetCategory {
  id: number;                     // valid as ReceiptUpload.category_id
  name: string;
  target_cents: Cents;            // 0 if no target set
  actual_cents: Cents;
}

export interface SnapshotTransaction {
  id: number;
  date: IsoDate;
  description: string;            // cleaned merchant/description, <= 100 chars
  amount_cents: Cents;            // negative = money out, positive = money in
  category_id: number | null;
  account_id: number;
}

export interface SnapshotAccount {
  id: number;
  name: string;                   // user's label, e.g. "Everyday checking"
  kind: 'checking' | 'savings' | 'brokerage' | 'credit_card' | 'cash' | 'loan'
      | 'retirement' | 'hsa' | 'other';
  balance_cents: Cents;           // counts transactions dated up to balance_as_of; negative = owed
  balance_as_of: IsoDate;
}

export interface TaxSummary {
  year: number;                   // current calendar tax year
  donations_total_cents: Cents;
  realized_gains: {
    short_term_cents: Cents;      // negative = loss
    long_term_cents: Cents;
    is_estimate: boolean;
  };
  deductions: { kind: string; label: string; amount_cents: Cents; is_estimate: boolean }[];
  disclaimer: string;             // plain-English "not tax advice, check with a pro" line
}

export interface SyncSettings {
  reminder_days_default: 1 | 2 | 3; // 2 unless changed on the dashboard
  reminder_days_allowed: [1, 2, 3];
}
```

Rules:
- `transactions`: last **60 days** up to and including today, newest first, at most **500**. No account
  numbers, notes, or raw bank memo fields.
- `accounts`: every account, whatever its kind. Never includes account numbers or `last4`. The phone may refuse a
  snapshot with more than 1,000 accounts or 1,000 categories in a group, or text over 100 characters (500 for the
  tax disclaimer).
  `credit_card` and `loan` balances are negative when money is owed.
- `budget.unassigned`: money from this month that couldn't be placed in a budget category (no category, or a
  refund), so the phone can say "N transactions need a category". `in_cents` and `out_cents` are both
  positive amounts; the phone treats a missing field as zeros.
- `deductions[].kind` is a stable key (`medical`, `education`, `home_office`, `hsa`, `business`, `other`, …);
  `label` is the display text. The phone shows unknown kinds using `label`.
- `deductions[].amount_cents` is the **amount recorded** (what the user spent or imported in that kind),
  not the amount the tax rules allow. Floors, limits, itemizing vs. the standard deduction, and
  employee vs. self-employed rules are not applied. The phone labels this section "Possibly deductible
  expenses" and must not present it as tax saved.
- `is_estimate: true` means "the Home Base is missing something" (e.g. a sale without a cost basis); the
  phone shows a small "missing info" tag.
- An empty database still produces a valid snapshot (zeros, empty arrays, three empty groups).

Money rules (how the server fills the totals; the phone trusts them and never re-derives them from
`transactions`):
- `income.received_cents` is the month's income transactions (clamped to 0 or more). Paychecks entered on
  the Home Base are never counted as received, so pay isn't counted twice. `expected_cents` is
  `received_cents` or the month's paycheck take-home, whichever is larger. Refunds, transfers between the
  user's own accounts, and balance adjustments are never income.
- Needs and wants `actual_cents` (group and category) are **net of refunds** in the same category, so a
  refund-heavy month can make them negative. They exclude transfers between the user's own accounts and
  balance adjustments.
- The savings `actual_cents` is money moved into savings this month **minus withdrawals**, so it can be
  negative when more came out than went in. It includes linked transfers from an everyday account into the
  user's own savings, brokerage, retirement or HSA account (minus transfers back out), which belong to no
  category, so the savings group's `actual_cents` can be more than its categories add up to.
- `transactions` still lists transfers, refunds and adjustments as they happened (sign = direction of
  money); they are for display only.
- `accounts[].balance_cents` is the account balance as of `balance_as_of`: transactions dated after today
  are left out. **Negative means money owed** (e.g. overdrawn checking, a credit card or loan balance).

### 5.2 Example

```json
{
  "contract": 1,
  "server_id": "Zk3pR7tQ1xYb9mWc2nLs5Q",
  "generated_at": "2026-10-02T18:30:00Z",
  "currency": "USD",
  "period": { "month": "2026-10", "start": "2026-10-01", "end": "2026-10-31", "days_elapsed": 2, "days_in_month": 31 },
  "income": {
    "expected_cents": 520000,
    "received_cents": 260000,
    "last_paycheck": { "pay_date": "2026-10-01", "net_cents": 260000 }
  },
  "budget": {
    "target_cents": 520000,
    "actual_cents": 171245,
    "groups": [
      {
        "group": "needs", "name": "Needs", "target_cents": 260000, "actual_cents": 158000,
        "categories": [
          { "id": 1, "name": "Rent", "target_cents": 150000, "actual_cents": 150000 },
          { "id": 2, "name": "Groceries", "target_cents": 60000, "actual_cents": 8000 }
        ]
      },
      {
        "group": "wants", "name": "Wants", "target_cents": 156000, "actual_cents": 3245,
        "categories": [ { "id": 7, "name": "Eating out", "target_cents": 30000, "actual_cents": 3245 } ]
      },
      {
        "group": "savings", "name": "Savings", "target_cents": 104000, "actual_cents": 10000,
        "categories": [ { "id": 12, "name": "Emergency fund", "target_cents": 50000, "actual_cents": 10000 } ]
      }
    ],
    "unassigned": { "in_cents": 0, "out_cents": 4200, "count": 2 }
  },
  "transactions": [
    { "id": 981, "date": "2026-10-02", "description": "Corner Cafe", "amount_cents": -3245, "category_id": 7, "account_id": 1 },
    { "id": 975, "date": "2026-10-01", "description": "Paycheck", "amount_cents": 260000, "category_id": null, "account_id": 1 }
  ],
  "accounts": [
    { "id": 1, "name": "Everyday checking", "kind": "checking", "balance_cents": 342150, "balance_as_of": "2026-10-02" },
    { "id": 2, "name": "Rainy day", "kind": "savings", "balance_cents": 1250000, "balance_as_of": "2026-09-30" }
  ],
  "tax": {
    "year": 2026,
    "donations_total_cents": 45000,
    "realized_gains": { "short_term_cents": -12000, "long_term_cents": 84000, "is_estimate": true },
    "deductions": [
      { "kind": "medical", "label": "Medical", "amount_cents": 23000, "is_estimate": false }
    ],
    "disclaimer": "These totals help you get ready for tax time. They aren't tax advice."
  },
  "settings": { "reminder_days_default": 2, "reminder_days_allowed": [1, 2, 3] }
}
```
