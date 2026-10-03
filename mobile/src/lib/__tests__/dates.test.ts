import { formatDay, formatLastSynced, formatMonth } from '../dates';

describe('formatMonth / formatDay', () => {
  it('formats months and days in plain words', () => {
    expect(formatMonth('2026-10')).toBe('October 2026');
    expect(formatDay('2026-10-02')).toBe('Oct 2');
    expect(formatDay('2026-01-31', 'long')).toBe('January 31');
  });

  it('falls back to the input when it is not a valid date', () => {
    expect(formatMonth('2026-13')).toBe('2026-13');
    expect(formatDay('soon')).toBe('soon');
  });
});

describe('formatLastSynced', () => {
  const now = new Date('2026-10-18T12:00:00Z');
  const ago = (ms: number) => new Date(now.getTime() - ms).toISOString();
  const MIN = 60_000;
  const HOUR = 60 * MIN;
  const DAY = 24 * HOUR;

  it('says "Never synced" when there is no sync', () => {
    expect(formatLastSynced(null, now)).toBe('Never synced');
    expect(formatLastSynced('not a date', now)).toBe('Never synced');
  });

  it('uses plain wording', () => {
    expect(formatLastSynced(ago(10_000), now)).toBe('Just now');
    expect(formatLastSynced(ago(MIN), now)).toBe('1 minute ago');
    expect(formatLastSynced(ago(5 * MIN), now)).toBe('5 minutes ago');
    expect(formatLastSynced(ago(HOUR), now)).toBe('1 hour ago');
    expect(formatLastSynced(ago(3 * HOUR), now)).toBe('3 hours ago');
    expect(formatLastSynced(ago(DAY), now)).toBe('Yesterday');
    expect(formatLastSynced(ago(2 * DAY + HOUR), now)).toBe('2 days ago');
  });

  it('treats a sync "in the future" (clock change) as just now', () => {
    expect(formatLastSynced(ago(-HOUR), now)).toBe('Just now');
  });
});
