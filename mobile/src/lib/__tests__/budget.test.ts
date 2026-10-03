import { SAMPLE_SNAPSHOT } from '../../sync/sampleSnapshot';
import type { Snapshot } from '../../sync/snapshot';
import {
  amountsText,
  barPercent,
  categoriesById,
  CLOSE_THRESHOLD_PERCENT,
  moneyDirection,
  monthHeadline,
  orderedGroups,
  percentUsed,
  recentTransactions,
  savingsStat,
  savingsStatus,
  spendingStatus,
  spentStat,
  statusText,
  transactionCategoryLabel,
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

describe('negative actuals (refunds bigger than spending, money out of savings)', () => {
  it.each([
    // [group, actual, target, status words, amounts]
    ['wants', -500, 10000, 'Refunds were more than spending by $5.00', 'Spent $0.00 of $100.00 (0%)'],
    ['needs', -1, 10000, 'Refunds were more than spending by $0.01', 'Spent $0.00 of $100.00 (0%)'],
    ['wants', -500, 0, 'Refunds were more than spending by $5.00', 'Spent $0.00'],
    ['savings', -10000, 104000, 'Took out $100.00', 'Saved $0.00 of $1,040.00 (0%)'],
    ['savings', -10000, 0, 'Took out $100.00', 'Saved $0.00'],
  ] as const)('%s %i of %i', (group, actual, target, words, amounts) => {
    expect(statusText(group, actual, target)).toBe(words);
    expect(amountsText(group, actual, target)).toBe(amounts);
  });

  it('never says more is left than the whole target', () => {
    expect(statusText('wants', -500, 10000)).not.toMatch(/left/);
  });

  it('headline: savings withdrawal shows "Took out", not a negative rate', () => {
    const s: Snapshot = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    s.budget.groups[2].actual_cents = -10000;
    const h = monthHeadline(s);
    expect(h.savedCents).toBe(-10000);
    expect(h.savingsRatePercent).toBeNull();
    expect(savingsStat(h)).toEqual({ value: 'Took out $100.00', note: 'More came out of savings than went in' });
  });

  it('headline: refunds bigger than all spending show $0.00 spent with a note', () => {
    const s: Snapshot = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    s.budget.groups[0].actual_cents = 0;
    s.budget.groups[1].actual_cents = -500;
    const h = monthHeadline(s);
    expect(spentStat(h)).toEqual({ value: '$0.00', note: 'Refunds were more than spending by $5.00' });
  });
});

describe('amountsText', () => {
  it('shows spent or saved against the target', () => {
    expect(amountsText('needs', 158000, 260000)).toBe('Spent $1,580.00 of $2,600.00 (60%)');
    expect(amountsText('savings', 60000, 104000)).toBe('Saved $600.00 of $1,040.00 (57%)');
    expect(amountsText('wants', 100, 0)).toBe('Spent $1.00');
  });
});

describe('headline stats', () => {
  it('words the sample month', () => {
    const h = monthHeadline(SAMPLE_SNAPSHOT);
    expect(spentStat(h)).toEqual({ value: '$2,960.27', note: 'of $4,160.00 planned' });
    expect(savingsStat(h)).toEqual({ value: '12%', note: 'of take-home pay ($600.00 saved)' });
  });

  it('says "Not yet" before any pay arrives', () => {
    const s: Snapshot = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    s.income.received_cents = 0;
    expect(savingsStat(monthHeadline(s))).toEqual({ value: 'Not yet', note: '$600.00 saved' });
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

  it('ignores the transaction list: transfers, refunds and adjustments never change the totals', () => {
    // The phone must never derive income or spending from `transactions` (finance review #8).
    // Totals come only from income.received_cents and the server's group actuals.
    const before = monthHeadline(SAMPLE_SNAPSHOT);
    const more: Snapshot = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    more.transactions.unshift(
      // Transfer between your own accounts, both legs.
      { id: 2001, date: '2026-10-18', description: 'Transfer to Rainy day', amount_cents: -25000, category_id: null, account_id: 1 },
      { id: 2002, date: '2026-10-18', description: 'Transfer from Everyday checking', amount_cents: 25000, category_id: null, account_id: 2 },
      // Refunds, categorised and not.
      { id: 2003, date: '2026-10-18', description: 'Shop refund', amount_cents: 4999, category_id: 8, account_id: 1 },
      { id: 2004, date: '2026-10-18', description: 'Refund', amount_cents: 1200, category_id: null, account_id: 1 },
      // Balance adjustments, both directions.
      { id: 2005, date: '2026-10-18', description: 'Balance adjustment', amount_cents: 731, category_id: null, account_id: 1 },
      { id: 2006, date: '2026-10-18', description: 'Balance adjustment', amount_cents: -731, category_id: null, account_id: 2 },
    );
    expect(monthHeadline(more)).toEqual(before);
  });

  it('zero income with spending: left to spend is target minus spent, no savings rate', () => {
    const s: Snapshot = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    s.income.received_cents = 0;
    const h = monthHeadline(s);
    expect(h.incomeReceivedCents).toBe(0);
    expect(h.spentCents).toBe(296027);
    expect(h.leftToSpendCents).toBe(416000 - 296027);
    expect(h.savingsRatePercent).toBeNull();
  });

  it('works on an empty-database snapshot', () => {
    const empty: Snapshot = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    empty.income = { expected_cents: 0, received_cents: 0, last_paycheck: null };
    empty.budget.target_cents = 0;
    empty.budget.actual_cents = 0;
    for (const g of empty.budget.groups) {
      g.target_cents = 0;
      g.actual_cents = 0;
      g.categories = [];
    }
    empty.transactions = [];
    empty.accounts = [];
    const h = monthHeadline(empty);
    expect(h).toEqual({
      incomeReceivedCents: 0,
      incomeExpectedCents: 0,
      spentCents: 0,
      spendingTargetCents: 0,
      leftToSpendCents: 0,
      isOverBudget: false,
      savedCents: 0,
      savingsRatePercent: null,
    });
    expect(spentStat(h)).toEqual({ value: '$0.00', note: 'of $0.00 planned' });
    expect(savingsStat(h)).toEqual({ value: 'Not yet', note: '$0.00 saved' });
    expect(recentTransactions(empty)).toEqual([]);
  });

  it('has no savings rate before any income arrives', () => {
    const none: Snapshot = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
    none.income.received_cents = 0;
    expect(monthHeadline(none).savingsRatePercent).toBeNull();
  });
});

describe('Recent activity labels', () => {
  const tx = (id: number) => SAMPLE_SNAPSHOT.transactions.find((t) => t.id === id)!;

  it('uses neutral money in / money out wording, never "Spent" or "Income"', () => {
    expect(moneyDirection(-1475)).toBe('Money out');
    expect(moneyDirection(-10000)).toBe('Money out'); // a move into savings is not spending
    expect(moneyDirection(260000)).toBe('Money in');
  });

  it('labels a move into savings with the savings group', () => {
    expect(transactionCategoryLabel(tx(1011), SAMPLE_SNAPSHOT)).toBe('Savings: Vacation fund');
    expect(transactionCategoryLabel(tx(1004), SAMPLE_SNAPSHOT)).toBe('Savings: Emergency fund');
  });

  it('uses the plain category name for spending', () => {
    expect(transactionCategoryLabel(tx(1015), SAMPLE_SNAPSHOT)).toBe('Eating out');
  });

  it('says "No category" for uncategorised rows whatever the sign', () => {
    expect(transactionCategoryLabel(tx(1012), SAMPLE_SNAPSHOT)).toBe('No category'); // paycheck
    const refund = { ...tx(1012), amount_cents: 2500, description: 'Store refund' };
    expect(transactionCategoryLabel(refund, SAMPLE_SNAPSHOT)).toBe('No category');
  });

  it('says "Other" for a category the snapshot does not list', () => {
    expect(transactionCategoryLabel({ ...tx(1015), category_id: 999 }, SAMPLE_SNAPSHOT)).toBe('Other');
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
