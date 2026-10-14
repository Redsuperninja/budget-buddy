/** Parsers for each part of a snapshot (groups, transactions, accounts, tax, settings). */

import {
  arr, bool, date, int, list, matching, MONTH, nonNegInt, obj, oneOf, SNAPSHOT_LIMITS, SnapshotError, str, text,
} from './snapshotChecks';
import { ACCOUNT_KINDS, GROUP_ORDER } from './snapshotTypes';
import type {
  BudgetCategory, BudgetGroup, Period, SnapshotAccount, SnapshotTransaction, SyncSettings, TaxSummary, Unassigned,
} from './snapshotTypes';

export function parseCategory(v: unknown, p: string): BudgetCategory {
  const o = obj(v, p);
  return {
    id: int(o.id, `${p}.id`),
    name: text(o.name, `${p}.name`),
    target_cents: int(o.target_cents, `${p}.target_cents`),
    actual_cents: int(o.actual_cents, `${p}.actual_cents`),
  };
}

export function parseGroup(v: unknown, p: string): BudgetGroup {
  const o = obj(v, p);
  return {
    group: oneOf(o.group, GROUP_ORDER, `${p}.group`),
    name: text(o.name, `${p}.name`),
    target_cents: int(o.target_cents, `${p}.target_cents`),
    actual_cents: int(o.actual_cents, `${p}.actual_cents`),
    categories: list(o.categories, `${p}.categories`, SNAPSHOT_LIMITS.categoriesPerGroup).map((c, i) =>
      parseCategory(c, `${p}.categories[${i}]`),
    ),
  };
}

export function parseTransaction(v: unknown, p: string): SnapshotTransaction {
  const o = obj(v, p);
  return {
    id: int(o.id, `${p}.id`),
    date: date(o.date, `${p}.date`),
    description: text(o.description, `${p}.description`),
    amount_cents: int(o.amount_cents, `${p}.amount_cents`),
    category_id: o.category_id === null ? null : int(o.category_id, `${p}.category_id`),
    account_id: int(o.account_id, `${p}.account_id`),
  };
}

/**
 * Returns null for an account kind this phone doesn't know yet. Contract §7.1 lets a newer
 * Home Base add enum values without bumping the version, so we skip that account rather than
 * rejecting the whole snapshot.
 */
/**
 * The month the snapshot covers. Its parts must agree (contract §5.1): `start` is the 1st, `end` is the
 * month's real last day (`days_in_month`, leap years included), and `days_elapsed` counts today, so 1 to
 * `days_in_month`. A mismatch would quietly mislabel the month, so it's refused like any bad field.
 */
export function parsePeriod(v: unknown, p: string): Period {
  const o = obj(v, p);
  const month = matching(o.month, MONTH, `${p}.month`, 'a month like 2026-10');
  const [year, monthNumber] = month.split('-').map(Number);
  if (monthNumber < 1 || monthNumber > 12) throw new SnapshotError(`${p}.month`, 'expected a month 01 to 12');
  const realDays = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate();
  const daysInMonth = int(o.days_in_month, `${p}.days_in_month`);
  if (daysInMonth !== realDays) throw new SnapshotError(`${p}.days_in_month`, `expected ${realDays} for ${month}`);
  const start = date(o.start, `${p}.start`);
  if (start !== `${month}-01`) throw new SnapshotError(`${p}.start`, `expected ${month}-01`);
  const end = date(o.end, `${p}.end`);
  if (end !== `${month}-${String(realDays).padStart(2, '0')}`) {
    throw new SnapshotError(`${p}.end`, `expected the last day of ${month}`);
  }
  const daysElapsed = int(o.days_elapsed, `${p}.days_elapsed`);
  if (daysElapsed < 1 || daysElapsed > daysInMonth) {
    throw new SnapshotError(`${p}.days_elapsed`, 'expected 1 to days_in_month');
  }
  return { month, start, end, days_elapsed: daysElapsed, days_in_month: daysInMonth };
}

export function parseAccount(v: unknown, p: string): SnapshotAccount | null {
  const o = obj(v, p);
  const kind = str(o.kind, `${p}.kind`);
  if (!(ACCOUNT_KINDS as readonly string[]).includes(kind)) return null;
  return {
    id: int(o.id, `${p}.id`),
    name: text(o.name, `${p}.name`),
    kind: kind as SnapshotAccount['kind'],
    balance_cents: int(o.balance_cents, `${p}.balance_cents`),
    balance_as_of: date(o.balance_as_of, `${p}.balance_as_of`),
  };
}

export function parseTax(v: unknown, p: string): TaxSummary {
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
    deductions: list(o.deductions, `${p}.deductions`, SNAPSHOT_LIMITS.deductions).map((d, i) => {
      const dp = `${p}.deductions[${i}]`;
      const dobj = obj(d, dp);
      return {
        kind: text(dobj.kind, `${dp}.kind`),
        label: text(dobj.label, `${dp}.label`),
        amount_cents: int(dobj.amount_cents, `${dp}.amount_cents`),
        is_estimate: bool(dobj.is_estimate, `${dp}.is_estimate`),
      };
    }),
    disclaimer: text(o.disclaimer, `${p}.disclaimer`, SNAPSHOT_LIMITS.disclaimer),
  };
}

export function parseSettings(v: unknown, p: string): SyncSettings {
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

/** `budget.unassigned` is optional (older Home Bases leave it out). */
export function parseUnassigned(v: unknown, p: string): Unassigned | undefined {
  if (v === undefined) return undefined;
  const o = obj(v, p);
  return {
    in_cents: nonNegInt(o.in_cents, `${p}.in_cents`),
    out_cents: nonNegInt(o.out_cents, `${p}.out_cents`),
    count: nonNegInt(o.count, `${p}.count`),
  };
}
