/**
 * Entry point for the budget snapshot the Home Base sends to the phone.
 *
 * `parseSnapshot()` checks untrusted JSON (from the local cache or the network) so a malformed
 * snapshot turns into a friendly message instead of a crash somewhere deep in a screen.
 * Types live in `snapshotTypes.ts`, field checks in `snapshotChecks.ts`, per-section parsers in
 * `snapshotSections.ts`. Per the contract, unknown extra fields are ignored (forward compatibility).
 */

import {
  arr, CURRENCY, date, int, ISO_DATE_TIME, matching, MONTH, nonNegInt, obj, Obj, SnapshotError, str,
} from './snapshotChecks';
import {
  parseAccount, parseGroup, parseSettings, parseTax, parseTransaction, parseUnassigned,
} from './snapshotSections';
import { GROUP_ORDER } from './snapshotTypes';
import type { Snapshot, SnapshotAccount } from './snapshotTypes';

export * from './snapshotTypes';

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

  const unassigned = parseUnassigned(budget.unassigned, 'budget.unassigned');

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
      ...(unassigned ? { unassigned } : {}),
    },
    transactions: arr(root.transactions, 'transactions').map((t, i) =>
      parseTransaction(t, `transactions[${i}]`),
    ),
    ...accountsOf(root),
    tax: parseTax(root.tax, 'tax'),
    settings: parseSettings(root.settings, 'settings'),
  };
}

/** The accounts this app can show, and how many it can't (also counting ones a saved copy skipped). */
function accountsOf(root: Record<string, unknown>): { accounts: SnapshotAccount[]; skipped_accounts?: number } {
  const raw = arr(root.accounts, 'accounts');
  const accounts = raw
    .map((a, i) => parseAccount(a, `accounts[${i}]`))
    .filter((a): a is SnapshotAccount => a !== null);
  const before = typeof root.skipped_accounts === 'number' && Number.isInteger(root.skipped_accounts)
    ? Math.max(0, root.skipped_accounts) : 0;
  const skipped = raw.length - accounts.length + before;
  return skipped > 0 ? { accounts, skipped_accounts: skipped } : { accounts };
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
