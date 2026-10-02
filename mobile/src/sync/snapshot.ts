/**
 * The budget snapshot the Home Base sends to the phone.
 *
 * Types mirror the sync contract v1, section 5 (`docs/api/sync-contract.md`) exactly, including
 * the snake_case field names used on the wire. `parseSnapshot()` checks untrusted JSON (from the
 * local cache today, from the network later) so a malformed snapshot turns into a friendly
 * message instead of a crash somewhere deep in a screen.
 *
 * Per the contract, unknown extra fields are ignored (forward compatibility).
 */

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
  };
  transactions: SnapshotTransaction[];
  accounts: SnapshotAccount[];
  tax: TaxSummary;
  settings: SyncSettings;
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

export interface SnapshotAccount {
  id: number;
  name: string; // user's label, e.g. "Everyday checking"
  kind: 'checking' | 'savings' | 'brokerage';
  balance_cents: Cents;
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

// ---------------------------------------------------------------------------
// Runtime validation
// ---------------------------------------------------------------------------

export type ParseResult =
  | { ok: true; snapshot: Snapshot }
  | {
      ok: false;
      /** Plain-English message that is safe to show the user. */
      message: string;
      /** Where the problem is (for a "Details" line / support), e.g. "budget.groups[1].actual_cents". */
      details: string;
    };

export const SNAPSHOT_INVALID_MESSAGE =
  "Your budget info couldn't be read. Tap Sync on your home Wi-Fi to get a fresh copy.";
export const SNAPSHOT_UPDATE_MESSAGE =
  'Budget Buddy needs an update on your phone or computer so they can talk to each other.';

class SnapshotError extends Error {
  constructor(readonly path: string, readonly problem: string) {
    super(`${path}: ${problem}`);
  }
}

type Obj = Record<string, unknown>;

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const MONTH = /^\d{4}-\d{2}$/;
// RFC 3339: date, time, optional fraction, then Z or an offset.
const ISO_DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;
const CURRENCY = /^[A-Z]{3}$/;

function obj(v: unknown, path: string): Obj {
  if (typeof v !== 'object' || v === null || Array.isArray(v)) {
    throw new SnapshotError(path, 'expected an object');
  }
  return v as Obj;
}

function arr(v: unknown, path: string): unknown[] {
  if (!Array.isArray(v)) throw new SnapshotError(path, 'expected a list');
  return v;
}

function str(v: unknown, path: string): string {
  if (typeof v !== 'string') throw new SnapshotError(path, 'expected text');
  return v;
}

function bool(v: unknown, path: string): boolean {
  if (typeof v !== 'boolean') throw new SnapshotError(path, 'expected true/false');
  return v;
}

function int(v: unknown, path: string): number {
  if (typeof v !== 'number' || !Number.isSafeInteger(v)) {
    throw new SnapshotError(path, 'expected a whole number');
  }
  return v;
}

function nonNegInt(v: unknown, path: string): number {
  const n = int(v, path);
  if (n < 0) throw new SnapshotError(path, 'expected zero or more');
  return n;
}

function matching(v: unknown, re: RegExp, path: string, what: string): string {
  const s = str(v, path);
  if (!re.test(s)) throw new SnapshotError(path, `expected ${what}`);
  return s;
}

const date = (v: unknown, p: string) => matching(v, ISO_DATE, p, 'a date like 2026-10-02');

function oneOf<T extends string | number>(v: unknown, allowed: readonly T[], path: string): T {
  if (!allowed.includes(v as T)) {
    throw new SnapshotError(path, `expected one of ${allowed.join(', ')}`);
  }
  return v as T;
}

function parseCategory(v: unknown, p: string): BudgetCategory {
  const o = obj(v, p);
  return {
    id: int(o.id, `${p}.id`),
    name: str(o.name, `${p}.name`),
    target_cents: int(o.target_cents, `${p}.target_cents`),
    actual_cents: int(o.actual_cents, `${p}.actual_cents`),
  };
}

function parseGroup(v: unknown, p: string): BudgetGroup {
  const o = obj(v, p);
  return {
    group: oneOf(o.group, GROUP_ORDER, `${p}.group`),
    name: str(o.name, `${p}.name`),
    target_cents: int(o.target_cents, `${p}.target_cents`),
    actual_cents: int(o.actual_cents, `${p}.actual_cents`),
    categories: arr(o.categories, `${p}.categories`).map((c, i) =>
      parseCategory(c, `${p}.categories[${i}]`),
    ),
  };
}

function parseTransaction(v: unknown, p: string): SnapshotTransaction {
  const o = obj(v, p);
  return {
    id: int(o.id, `${p}.id`),
    date: date(o.date, `${p}.date`),
    description: str(o.description, `${p}.description`),
    amount_cents: int(o.amount_cents, `${p}.amount_cents`),
    category_id: o.category_id === null ? null : int(o.category_id, `${p}.category_id`),
    account_id: int(o.account_id, `${p}.account_id`),
  };
}

function parseAccount(v: unknown, p: string): SnapshotAccount {
  const o = obj(v, p);
  return {
    id: int(o.id, `${p}.id`),
    name: str(o.name, `${p}.name`),
    kind: oneOf(o.kind, ['checking', 'savings', 'brokerage'] as const, `${p}.kind`),
    balance_cents: int(o.balance_cents, `${p}.balance_cents`),
    balance_as_of: date(o.balance_as_of, `${p}.balance_as_of`),
  };
}

function parseTax(v: unknown, p: string): TaxSummary {
  const o = obj(v, p);
  const g = obj(o.realized_gains, `${p}.realized_gains`);
  return {
    year: int(o.year, `${p}.year`),
    donations_total_cents: int(o.donations_total_cents, `${p}.donations_total_cents`),
    realized_gains: {
      short_term_cents: int(g.short_term_cents, `${p}.realized_gains.short_term_cents`),
      long_term_cents: int(g.long_term_cents, `${p}.realized_gains.long_term_cents`),
      is_estimate: bool(g.is_estimate, `${p}.realized_gains.is_estimate`),
    },
    deductions: arr(o.deductions, `${p}.deductions`).map((d, i) => {
      const dp = `${p}.deductions[${i}]`;
      const dobj = obj(d, dp);
      return {
        kind: str(dobj.kind, `${dp}.kind`),
        label: str(dobj.label, `${dp}.label`),
        amount_cents: int(dobj.amount_cents, `${dp}.amount_cents`),
        is_estimate: bool(dobj.is_estimate, `${dp}.is_estimate`),
      };
    }),
    disclaimer: str(o.disclaimer, `${p}.disclaimer`),
  };
}

function parseSettings(v: unknown, p: string): SyncSettings {
  const o = obj(v, p);
  const days = [1, 2, 3] as const;
  const allowed = arr(o.reminder_days_allowed, `${p}.reminder_days_allowed`);
  allowed.forEach((d, i) => oneOf(d, days, `${p}.reminder_days_allowed[${i}]`));
  return {
    reminder_days_default: oneOf(o.reminder_days_default, days, `${p}.reminder_days_default`),
    // The contract types this as exactly [1, 2, 3]. We only check each entry is 1–3, so a
    // narrower list from a future Home Base doesn't make the whole snapshot unreadable.
    reminder_days_allowed: allowed as SyncSettings['reminder_days_allowed'],
  };
}

function parseOrThrow(input: unknown): Snapshot {
  const root = obj(input, 'snapshot');

  const period = obj(root.period, 'period');
  const daysInMonth = int(period.days_in_month, 'period.days_in_month');
  if (daysInMonth < 28 || daysInMonth > 31) {
    throw new SnapshotError('period.days_in_month', 'expected 28 to 31');
  }
  const daysElapsed = int(period.days_elapsed, 'period.days_elapsed');
  if (daysElapsed < 0 || daysElapsed > daysInMonth) {
    throw new SnapshotError('period.days_elapsed', 'expected 0 to days_in_month');
  }

  const income = obj(root.income, 'income');
  let lastPaycheck: Snapshot['income']['last_paycheck'] = null;
  if (income.last_paycheck !== null) {
    const lp = obj(income.last_paycheck, 'income.last_paycheck');
    lastPaycheck = {
      pay_date: date(lp.pay_date, 'income.last_paycheck.pay_date'),
      net_cents: int(lp.net_cents, 'income.last_paycheck.net_cents'),
    };
  }

  const budget = obj(root.budget, 'budget');
  const groups = arr(budget.groups, 'budget.groups').map((g, i) =>
    parseGroup(g, `budget.groups[${i}]`),
  );
  for (const key of GROUP_ORDER) {
    if (groups.filter((g) => g.group === key).length !== 1) {
      throw new SnapshotError('budget.groups', `expected exactly one "${key}" group`);
    }
  }

  return {
    contract: 1,
    server_id: str(root.server_id, 'server_id'),
    generated_at: matching(root.generated_at, ISO_DATE_TIME, 'generated_at', 'a date-time'),
    currency: matching(root.currency, CURRENCY, 'currency', 'a currency code like USD'),
    period: {
      month: matching(period.month, MONTH, 'period.month', 'a month like 2026-10'),
      start: date(period.start, 'period.start'),
      end: date(period.end, 'period.end'),
      days_elapsed: daysElapsed,
      days_in_month: daysInMonth,
    },
    income: {
      expected_cents: nonNegInt(income.expected_cents, 'income.expected_cents'),
      received_cents: nonNegInt(income.received_cents, 'income.received_cents'),
      last_paycheck: lastPaycheck,
    },
    budget: {
      target_cents: int(budget.target_cents, 'budget.target_cents'),
      actual_cents: int(budget.actual_cents, 'budget.actual_cents'),
      groups,
    },
    transactions: arr(root.transactions, 'transactions').map((t, i) =>
      parseTransaction(t, `transactions[${i}]`),
    ),
    accounts: arr(root.accounts, 'accounts').map((a, i) => parseAccount(a, `accounts[${i}]`)),
    tax: parseTax(root.tax, 'tax'),
    settings: parseSettings(root.settings, 'settings'),
  };
}

/**
 * Check that `input` (already JSON-parsed) is a valid v1 snapshot.
 * Returns a cleaned copy (unknown fields dropped) or a friendly error. Never throws.
 */
export function parseSnapshot(input: unknown): ParseResult {
  try {
    const contract = typeof input === 'object' && input !== null ? (input as Obj).contract : undefined;
    if (typeof contract === 'number' && Number.isInteger(contract) && contract > 1) {
      return { ok: false, message: SNAPSHOT_UPDATE_MESSAGE, details: `contract: ${contract}` };
    }
    if (contract !== 1) {
      return { ok: false, message: SNAPSHOT_INVALID_MESSAGE, details: 'contract: expected 1' };
    }
    return { ok: true, snapshot: parseOrThrow(input) };
  } catch (e) {
    const details = e instanceof SnapshotError ? e.message : 'unexpected error';
    return { ok: false, message: SNAPSHOT_INVALID_MESSAGE, details };
  }
}

/** Type guard form of `parseSnapshot`. */
export function isSnapshot(input: unknown): input is Snapshot {
  return parseSnapshot(input).ok;
}
