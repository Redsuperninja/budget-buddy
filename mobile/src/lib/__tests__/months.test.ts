import { oldMonthNotice, phoneMonth, withMonthBreaks } from '../months';

const at = (y: number, m: number, d = 15) => new Date(y, m - 1, d, 12);

describe('oldMonthNotice', () => {
  it('says nothing when the summary is this month', () => {
    expect(oldMonthNotice('2026-10', at(2026, 10))).toBeNull();
  });

  it('names both months when the summary is older', () => {
    expect(oldMonthNotice('2026-09', at(2026, 10, 2))).toBe(
      'This is your September summary. Sync on your home Wi-Fi to see October.',
    );
  });

  it('adds the years across a new year', () => {
    expect(oldMonthNotice('2026-12', at(2027, 1, 1))).toBe(
      'This is your December 2026 summary. Sync on your home Wi-Fi to see January 2027.',
    );
  });

  it('uses the phone calendar for its month', () => {
    expect(phoneMonth(at(2026, 3, 31))).toBe('2026-03');
  });
});

describe('withMonthBreaks', () => {
  it('labels rows from another month, once per month', () => {
    const rows = [{ date: '2026-10-02' }, { date: '2026-09-30' }, { date: '2026-09-12' }, { date: '2026-08-31' }];
    expect(withMonthBreaks(rows, '2026-10')).toEqual([
      { kind: 'item', item: rows[0] },
      { kind: 'month', label: 'September 2026' },
      { kind: 'item', item: rows[1] },
      { kind: 'item', item: rows[2] },
      { kind: 'month', label: 'August 2026' },
      { kind: 'item', item: rows[3] },
    ]);
  });

  it('labels the first row too when none are from this month', () => {
    expect(withMonthBreaks([{ date: '2026-09-30' }], '2026-10')[0]).toEqual({ kind: 'month', label: 'September 2026' });
  });

  it('adds nothing when every row is from this month', () => {
    expect(withMonthBreaks([{ date: '2026-10-05' }], '2026-10')).toEqual([{ kind: 'item', item: { date: '2026-10-05' } }]);
  });
});
