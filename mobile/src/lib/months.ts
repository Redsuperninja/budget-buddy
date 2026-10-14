/**
 * Keeping old numbers from passing as this month's (issue #23): a notice when the saved summary is
 * from another month than the phone's, and month labels between recent transactions from different
 * months. Pure functions; `now` is the phone's local time.
 */

import { formatMonth } from '@/lib/dates';

/** The phone's current month as "2026-10", on its own calendar. */
export function phoneMonth(now: Date = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

const monthName = (month: string) => formatMonth(month).split(' ')[0];

/**
 * "This is your September summary. Sync on your home Wi-Fi to see October." when the summary's
 * month isn't the phone's month, else null.
 */
export function oldMonthNotice(summaryMonth: string, now: Date = new Date()): string | null {
  const current = phoneMonth(now);
  if (summaryMonth === current) return null;
  const sameYear = summaryMonth.slice(0, 4) === current.slice(0, 4);
  const was = sameYear ? monthName(summaryMonth) : formatMonth(summaryMonth);
  const is = sameYear ? monthName(current) : formatMonth(current);
  return `This is your ${was} summary. Sync on your home Wi-Fi to see ${is}.`;
}

export type MonthBreak<T> = { kind: 'month'; label: string } | { kind: 'item'; item: T };

/**
 * Items (newest first) with a month label before the first one of each month that isn't
 * `currentMonth`, so last month's rows don't read as this month's.
 */
export function withMonthBreaks<T extends { date: string }>(items: T[], currentMonth: string): MonthBreak<T>[] {
  const out: MonthBreak<T>[] = [];
  let shown = currentMonth;
  for (const item of items) {
    const month = item.date.slice(0, 7);
    if (month !== shown) {
      out.push({ kind: 'month', label: formatMonth(month) });
      shown = month;
    }
    out.push({ kind: 'item', item });
  }
  return out;
}
