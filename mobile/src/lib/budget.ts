/**
 * Budget breakdown math for the Home screen. Pure functions on integer cents, no React.
 *
 * Definitions (reviewed by finance-tax-expert before merge):
 * - "Spent" = actual of the spending groups (Needs + Wants). Savings is money kept, not spent.
 * - "Left to spend" = spending targets (Needs + Wants) minus spent. Negative means over budget.
 * - "Savings rate" = saved this month ÷ take-home received this month.
 *
 * Rounding: "percent used" is rounded DOWN to a whole number (Math.floor), never up, so the number
 * stays on the same side of each threshold as the status words (89.6% shows 89%, "On track";
 * 99.6% shows 99%, "Close to the limit"). Anything over the target shows at least 101%, so
 * "Over by $0.40" never sits next to "(100%)". Negative actuals (refunds bigger than spending, or
 * money taken out of savings) show 0%.
 */
import { formatCents } from './money';
import type { BudgetCategory, BudgetGroup, GroupKey, Snapshot, SnapshotTransaction } from '../sync/snapshot';

/** At or above this share of a spending target, a line is "close" to its limit. */
export const CLOSE_THRESHOLD_PERCENT = 90;

export type SpendingStatus = 'on_track' | 'close' | 'over' | 'no_target';
export type SavingsStatus = 'goal_met' | 'in_progress' | 'no_target';
export type LineStatus = SpendingStatus | SavingsStatus;

/**
 * Whole-number percent of target used, rounded down (e.g. 61). Can exceed 100; anything over the
 * target is at least 101. Never below 0. Returns null when there's no target (target <= 0),
 * since a percent would be meaningless.
 */
export function percentUsed(actualCents: number, targetCents: number): number | null {
  if (targetCents <= 0) return null;
  if (actualCents <= 0) return 0;
  const pct = Math.floor((actualCents * 100) / targetCents);
  return actualCents > targetCents && pct <= 100 ? 101 : pct;
}

/** Width for a progress bar, 0–100 (overspending fills the bar, it doesn't overflow). */
export function barPercent(actualCents: number, targetCents: number): number {
  if (targetCents <= 0) return actualCents > 0 ? 100 : 0;
  return Math.min(100, Math.max(0, (actualCents * 100) / targetCents));
}

/** Status of a spending line (Needs, Wants, or one of their categories). */
export function spendingStatus(actualCents: number, targetCents: number): SpendingStatus {
  if (targetCents <= 0) return 'no_target';
  if (actualCents > targetCents) return 'over';
  if (actualCents * 100 >= targetCents * CLOSE_THRESHOLD_PERCENT) return 'close';
  return 'on_track';
}

/** Status of a savings line (more is better, so it can't be "over"). */
export function savingsStatus(actualCents: number, targetCents: number): SavingsStatus {
  if (targetCents <= 0) return 'no_target';
  return actualCents >= targetCents ? 'goal_met' : 'in_progress';
}

export function lineStatus(group: GroupKey, actualCents: number, targetCents: number): LineStatus {
  return group === 'savings'
    ? savingsStatus(actualCents, targetCents)
    : spendingStatus(actualCents, targetCents);
}

/**
 * Plain-English status text, so meaning never depends on colour alone.
 * e.g. "Over by $42.00", "$300.00 left", "Close to the limit: $25.00 left", "$400.00 to go".
 */
export function statusText(
  group: GroupKey,
  actualCents: number,
  targetCents: number,
  currency = 'USD',
): string {
  const fmt = (c: number) => formatCents(c, currency);
  // A negative actual is a refund-heavy month (spending) or a withdrawal (savings).
  // Say so plainly instead of claiming more is "left" than the whole target.
  if (actualCents < 0) {
    return group === 'savings'
      ? `Took out ${fmt(-actualCents)}`
      : `Refunds were more than spending by ${fmt(-actualCents)}`;
  }
  const status = lineStatus(group, actualCents, targetCents);
  switch (status) {
    case 'over':
      return `Over by ${fmt(actualCents - targetCents)}`;
    case 'close':
      return actualCents === targetCents
        ? 'Right at the limit'
        : `Close to the limit: ${fmt(targetCents - actualCents)} left`;
    case 'on_track':
      return `On track: ${fmt(targetCents - actualCents)} left`;
    case 'goal_met':
      return 'Goal reached';
    case 'in_progress':
      return `${fmt(targetCents - actualCents)} to go`;
    case 'no_target':
      return group === 'savings' ? 'No goal set' : 'No limit set';
  }
}

/**
 * "Spent $1,580.00 of $2,600.00 (60%)" or "Saved ...". A negative actual is shown as $0.00 / 0%;
 * statusText explains why (refunds, or money taken out of savings).
 */
export function amountsText(
  group: GroupKey,
  actualCents: number,
  targetCents: number,
  currency = 'USD',
): string {
  const verb = group === 'savings' ? 'Saved' : 'Spent';
  const actual = formatCents(Math.max(0, actualCents), currency);
  if (targetCents <= 0) return `${verb} ${actual}`;
  const pct = percentUsed(actualCents, targetCents);
  return `${verb} ${actual} of ${formatCents(targetCents, currency)} (${pct}%)`;
}

export type MonthHeadline = {
  /** Take-home received so far this month. */
  incomeReceivedCents: number;
  /** Take-home expected this month. */
  incomeExpectedCents: number;
  /** Needs + Wants actual. */
  spentCents: number;
  /** Needs + Wants targets. */
  spendingTargetCents: number;
  /** Spending target minus spent. Negative = over budget. */
  leftToSpendCents: number;
  isOverBudget: boolean;
  /** Savings group actual. */
  savedCents: number;
  /**
   * Whole-number percent of received income saved, or null if nothing received yet or if more
   * was taken out of savings than put in (savedCents < 0).
   */
  savingsRatePercent: number | null;
};

export function monthHeadline(snapshot: Snapshot): MonthHeadline {
  let spentCents = 0;
  let spendingTargetCents = 0;
  let savedCents = 0;
  for (const g of snapshot.budget.groups) {
    if (g.group === 'savings') {
      savedCents += g.actual_cents;
    } else {
      spentCents += g.actual_cents;
      spendingTargetCents += g.target_cents;
    }
  }
  const received = snapshot.income.received_cents;
  const leftToSpendCents = spendingTargetCents - spentCents;
  return {
    incomeReceivedCents: received,
    incomeExpectedCents: snapshot.income.expected_cents,
    spentCents,
    spendingTargetCents,
    leftToSpendCents,
    isOverBudget: leftToSpendCents < 0,
    savedCents,
    savingsRatePercent:
      received > 0 && savedCents >= 0 ? Math.round((savedCents * 100) / received) : null,
  };
}

export type StatText = { value: string; note: string };

/** "Spent" stat on the Home headline. Refunds bigger than spending show $0.00 with a note. */
export function spentStat(h: MonthHeadline, currency = 'USD'): StatText {
  const fmt = (c: number) => formatCents(c, currency);
  if (h.spentCents < 0) {
    return {
      value: fmt(0),
      note: `Refunds were more than spending by ${fmt(-h.spentCents)}`,
    };
  }
  return { value: fmt(h.spentCents), note: `of ${fmt(h.spendingTargetCents)} planned` };
}

/** "Savings rate" stat on the Home headline. */
export function savingsStat(h: MonthHeadline, currency = 'USD'): StatText {
  const fmt = (c: number) => formatCents(c, currency);
  if (h.savedCents < 0) {
    return { value: `Took out ${fmt(-h.savedCents)}`, note: 'More came out of savings than went in' };
  }
  if (h.savingsRatePercent === null) {
    return { value: 'Not yet', note: `${fmt(h.savedCents)} saved` };
  }
  return { value: `${h.savingsRatePercent}%`, note: `of take-home pay (${fmt(h.savedCents)} saved)` };
}

/** Groups in the standard order (Needs, Wants, Savings), whatever order they arrived in. */
export function orderedGroups(snapshot: Snapshot): BudgetGroup[] {
  const order: GroupKey[] = ['needs', 'wants', 'savings'];
  return [...snapshot.budget.groups].sort((a, b) => order.indexOf(a.group) - order.indexOf(b.group));
}

/** Map of category id → category, for labelling transactions. */
export function categoriesById(snapshot: Snapshot): Map<number, BudgetCategory> {
  const map = new Map<number, BudgetCategory>();
  for (const g of snapshot.budget.groups) for (const c of g.categories) map.set(c.id, c);
  return map;
}

/**
 * Neutral screen-reader word for a transaction's direction. A negative amount isn't always
 * spending (it may be a move into savings) and a positive one isn't always income (it may be a
 * refund, a transfer back, or an adjustment), so we don't guess.
 */
export function moneyDirection(amountCents: number): 'Money in' | 'Money out' {
  return amountCents > 0 ? 'Money in' : 'Money out';
}

/**
 * Category label for a Recent activity row. Categories in the savings group are prefixed with the
 * group name ("Savings: Vacation fund") so a move into savings doesn't look like spending.
 * No category is "No category" whatever the sign: we can't tell income from a refund or transfer.
 */
export function transactionCategoryLabel(tx: SnapshotTransaction, snapshot: Snapshot): string {
  if (tx.category_id === null) return 'No category';
  for (const g of snapshot.budget.groups) {
    const c = g.categories.find((cat) => cat.id === tx.category_id);
    if (c) return g.group === 'savings' ? `${g.name}: ${c.name}` : c.name;
  }
  return 'Other';
}

/** The most recent transactions, newest first (ties keep the snapshot's order). */
export function recentTransactions(snapshot: Snapshot, limit = 10): SnapshotTransaction[] {
  return [...snapshot.transactions]
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
    .slice(0, limit);
}
