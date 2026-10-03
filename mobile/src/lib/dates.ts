/** Date wording for people, not computers. Pure functions, no locale surprises. */

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

/** "2026-10" -> "October 2026". Falls back to the input if it isn't a valid month. */
export function formatMonth(month: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(month);
  const idx = m ? Number(m[2]) - 1 : -1;
  return m && idx >= 0 && idx < 12 ? `${MONTHS[idx]} ${m[1]}` : month;
}

/** "2026-10-02" -> "Oct 2" (short) or "October 2" (long). Falls back to the input. */
export function formatDay(date: string, style: 'short' | 'long' = 'short'): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  const idx = m ? Number(m[2]) - 1 : -1;
  if (!m || idx < 0 || idx >= 12) return date;
  const name = style === 'short' ? MONTHS[idx].slice(0, 3) : MONTHS[idx];
  return `${name} ${Number(m[3])}`;
}

/**
 * How long ago the phone last synced, in plain words:
 * "Never synced", "Just now", "5 minutes ago", "3 hours ago", "Yesterday", "2 days ago".
 */
export function formatLastSynced(lastSyncedAt: string | null, now: Date = new Date()): string {
  if (lastSyncedAt === null) return 'Never synced';
  const then = Date.parse(lastSyncedAt);
  if (Number.isNaN(then)) return 'Never synced';
  const minutes = Math.floor((now.getTime() - then) / 60_000);
  if (minutes < 1) return 'Just now'; // also covers a phone clock that moved backwards
  if (minutes < 60) return minutes === 1 ? '1 minute ago' : `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours === 1 ? '1 hour ago' : `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? 'Yesterday' : `${days} days ago`;
}
