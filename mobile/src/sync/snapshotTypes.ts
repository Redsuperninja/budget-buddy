/** Snapshot types, mirroring the sync contract v1 section 5 (docs/api/sync-contract.md), snake_case and all. */

type Cents = number; // integer
type IsoDate = string; // "YYYY-MM-DD"
type IsoDateTime = string; // "2026-10-02T18:30:00Z"

export interface Snapshot {
  contract: 1;
  server_id: string;
  generated_at: IsoDateTime;
  currency: string; // ISO 4217, e.g. "USD"
  period: {
    month: string; // "2026-10"
    start: IsoDate; // first day of month
    end: IsoDate; // last day of month
    days_elapsed: number; // including today
    days_in_month: number;
  };
  income: {
    expected_cents: Cents; // this month's expected take-home (from paychecks)
    received_cents: Cents; // take-home received so far this month
    last_paycheck: { pay_date: IsoDate; net_cents: Cents } | null;
  };
  budget: {
    target_cents: Cents; // sum of group targets
    actual_cents: Cents; // sum of group actuals
    groups: BudgetGroup[]; // always needs, wants, savings in that order
    /** Transactions with no category yet. NOT counted in the totals above. Absent on older Home Bases. */
    unassigned?: Unassigned;
  };
  transactions: SnapshotTransaction[];
  accounts: SnapshotAccount[];
  tax: TaxSummary;
  settings: SyncSettings;
}

export interface Unassigned {
  in_cents: Cents; // >= 0
  out_cents: Cents; // >= 0
  count: number; // >= 0
}

export interface BudgetGroup {
  group: 'needs' | 'wants' | 'savings';
  name: string; // display name, e.g. "Needs"
  target_cents: Cents;
  actual_cents: Cents; // spent (needs/wants) or saved (savings) this month, >= 0 normally
  categories: BudgetCategory[];
}

export interface BudgetCategory {
  id: number; // valid as ReceiptUpload.category_id
  name: string;
  target_cents: Cents; // 0 if no target set
  actual_cents: Cents;
}

export interface SnapshotTransaction {
  id: number;
  date: IsoDate;
  description: string; // cleaned merchant/description, <= 100 chars
  amount_cents: Cents; // negative = money out, positive = money in
  category_id: number | null;
  account_id: number;
}

export const ACCOUNT_KINDS = [
  'checking',
  'savings',
  'brokerage',
  'credit_card',
  'cash',
  'loan',
  'retirement',
  'hsa',
  'other',
] as const;
export type AccountKind = (typeof ACCOUNT_KINDS)[number];

export interface SnapshotAccount {
  id: number;
  name: string; // user's label, e.g. "Everyday checking"
  kind: AccountKind;
  balance_cents: Cents; // credit_card / loan: negative = money owed
  balance_as_of: IsoDate;
}

export interface TaxDeduction {
  kind: string;
  label: string;
  amount_cents: Cents;
  is_estimate: boolean;
}

export interface TaxSummary {
  year: number; // current calendar tax year
  donations_total_cents: Cents;
  realized_gains: {
    short_term_cents: Cents; // negative = loss
    long_term_cents: Cents;
    is_estimate: boolean;
  };
  deductions: TaxDeduction[];
  disclaimer: string; // plain-English "not tax advice, check with a pro" line
}

export interface SyncSettings {
  reminder_days_default: 1 | 2 | 3; // 2 unless changed on the dashboard
  reminder_days_allowed: [1, 2, 3];
}

export type GroupKey = BudgetGroup['group'];
export const GROUP_ORDER: readonly GroupKey[] = ['needs', 'wants', 'savings'];
