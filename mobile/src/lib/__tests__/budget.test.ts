import { SAMPLE_SNAPSHOT } from '../../sync/sampleSnapshot';
import type { Snapshot } from '../../sync/snapshot';
import {
  barPercent,
  categoriesById,
  CLOSE_THRESHOLD_PERCENT,
  monthHeadline,
  orderedGroups,
  percentUsed,
  recentTransactions,
  savingsStatus,
  spendingStatus,
  statusText,
} from '../budget';

describe('percentUsed', () => {
  it('rounds down to a whole percent', () => {
    expect(percentUsed(158000, 260000)).toBe(60); // 60.77%
    expect(percentUsed(1, 3)).toBe(33);
    expect(percentUsed(2, 3)).toBe(66);
  });

  it.each([
    // [actual, target, percent, status]
    [8960, 10000, 89, 'on_track'],
    [8999, 10000, 89, 'on_track'],
    [9000, 10000, 90, 'close'],
    [9960, 10000, 99, 'close'],
    [10000, 10000, 100, 'close'],
    [10001, 10000, 101, 'over'],
    [10040, 10000, 101, 'over'],
    [10100, 10000, 101, 'over'],
    [10199, 10000, 101, 'over'],
    [10250, 10000, 102, 'over'],
  ])('%i of %i shows %i%% and agrees with the status (%s)', (actual, target, pct, status) => {
    expect(percentUsed(actual, target)).toBe(pct);
    expect(spendingStatus(actual, target)).toBe(status);
  });

  it('never goes below 0', () => {
    expect(percentUsed(-500, 10000)).toBe(0);
    expect(percentUsed(0, 10000)).toBe(0);
  });

  it('can go over 100', () => {
    expect(percentUsed(34200, 30000)).toBe(114);
  });

  it('is null when there is no target', () => {
    expect(percentUsed(500, 0)).toBeNull();
    expect(percentUsed(0, 0)).toBeNull();
  });
});

describe('barPercent', () => {
  it('caps at 100 and floors at 0', () => {
    expect(barPercent(50, 100)).toBe(50);
    expect(barPercent(250, 100)).toBe(100);
    expect(barPercent(-10, 100)).toBe(0);
  });

  it('fills when spending with no target, empty otherwise', () => {
    expect(barPercent(1, 0)).toBe(100);
    expect(barPercent(0, 0)).toBe(0);
  });
});

describe('spendingStatus', () => {
  it('uses the close threshold', () => {
    expect(CLOSE_THRESHOLD_PERCENT).toBe(90);
    expect(spendingStatus(8999, 10000)).toBe('on_track');
    expect(spendingStatus(9000, 10000)).toBe('close');
    expect(spendingStatus(10000, 10000)).toBe('close');
    expect(spendingStatus(10001, 10000)).toBe('over');
  });

  it('handles no target', () => {
    expect(spendingStatus(500, 0)).toBe('no_target');
  });
});

describe('savingsStatus', () => {
  it('is never "over"', () => {
    expect(savingsStatus(0, 10000)).toBe('in_progress');
    expect(savingsStatus(10000, 10000)).toBe('goal_met');
    expect(savingsStatus(25000, 10000)).toBe('goal_met');
    expect(savingsStatus(100, 0)).toBe('no_target');
  });
});

describe('statusText', () => {
  it('says how much over, in words', () => {
    expect(statusText('wants', 34200, 30000)).toBe('Over by $42.00');
  });

  it('says how much is left', () => {
    expect(statusText('needs', 158000, 260000)).toBe('On track: $1,020.00 left');
    expect(statusText('needs', 9500, 10000)).toBe('Close to the limit: $5.00 left');
    expect(statusText('needs', 10000, 10000)).toBe('Right at the limit');
  });

  it('words savings as progress toward a goal', () => {
    expect(statusText('savings', 60000, 104000)).toBe('$440.00 to go');
    expect(statusText('savings', 50000, 50000)).toBe('Goal reached');
  });

  it('handles no target', () => {
    expect(statusText('wants', 100, 0)).toBe('No limit set');
    expect(statusText('savings', 100, 0)).toBe('No goal set');
  });
});

describe('monthHeadline', () => {
  it('works out the sample month', () => {
    expect(monthHeadline(SAMPLE_SNAPSHOT)).toEqual({
      incomeReceivedCents: 520000,
      incomeExpectedCents: 520000,
      spentCents: 225680 + 70347,
      spendingTargetCents: 260000 + 156000,
      leftToSpendCents: 416000 - 296027,
      isOverBudget: false,
      savedCents: 60000,
      savingsRatePercent: 12, // 60000 / 520000 = 11.5% -> 12
    });
  });

  it('flags over budget with a negative left-to-spend', () => {
    const over: Snapshot = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    over.budget.groups[1].actual_cents = 300000;
    const h = monthHeadline(over);
    expect(h.isOverBudget).toBe(true);
    expect(h.leftToSpendCents).toBe(416000 - (225680 + 300000));
  });

  it('has no savings rate before any income arrives', () => {
    const none: Snapshot = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    none.income.received_cents = 0;
    expect(monthHeadline(none).savingsRatePercent).toBeNull();
  });
});

describe('sample snapshot is self-consistent', () => {
  it('group totals equal their categories, budget totals equal the groups', () => {
    let target = 0;
    let actual = 0;
    for (const g of SAMPLE_SNAPSHOT.budget.groups) {
      expect(g.categories.reduce((s, c) => s + c.target_cents, 0)).toBe(g.target_cents);
      expect(g.categories.reduce((s, c) => s + c.actual_cents, 0)).toBe(g.actual_cents);
      target += g.target_cents;
      actual += g.actual_cents;
    }
    expect(target).toBe(SAMPLE_SNAPSHOT.budget.target_cents);
    expect(actual).toBe(SAMPLE_SNAPSHOT.budget.actual_cents);
  });
});

describe('helpers', () => {
  it('orders groups needs, wants, savings', () => {
    const shuffled: Snapshot = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    shuffled.budget.groups.reverse();
    expect(orderedGroups(shuffled).map((g) => g.group)).toEqual(['needs', 'wants', 'savings']);
  });

  it('looks up categories by id', () => {
    expect(categoriesById(SAMPLE_SNAPSHOT).get(6)?.name).toBe('Eating out');
  });

  it('returns the newest 10 transactions, newest first', () => {
    const recent = recentTransactions(SAMPLE_SNAPSHOT);
    expect(recent).toHaveLength(10);
    expect(recent[0].date).toBe('2026-10-18');
    const dates = recent.map((t) => t.date);
    expect([...dates].sort().reverse()).toEqual(dates);
  });
});
