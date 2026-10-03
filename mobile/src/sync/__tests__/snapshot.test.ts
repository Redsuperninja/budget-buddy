import { SAMPLE_SNAPSHOT } from '../sampleSnapshot';
import {
  isSnapshot,
  parseSnapshot,
  SNAPSHOT_INVALID_MESSAGE,
  SNAPSHOT_UPDATE_MESSAGE,
} from '../snapshot';

/** The example from docs/api/sync-contract.md §5.2, verbatim. */
const CONTRACT_EXAMPLE = {
  contract: 1,
  server_id: 'Zk3pR7tQ1xYb9mWc2nLs5Q',
  generated_at: '2026-10-02T18:30:00Z',
  currency: 'USD',
  period: { month: '2026-10', start: '2026-10-01', end: '2026-10-31', days_elapsed: 2, days_in_month: 31 },
  income: {
    expected_cents: 520000,
    received_cents: 260000,
    last_paycheck: { pay_date: '2026-10-01', net_cents: 260000 },
  },
  budget: {
    target_cents: 520000,
    actual_cents: 171245,
    groups: [
      {
        group: 'needs', name: 'Needs', target_cents: 260000, actual_cents: 158000,
        categories: [
          { id: 1, name: 'Rent', target_cents: 150000, actual_cents: 150000 },
          { id: 2, name: 'Groceries', target_cents: 60000, actual_cents: 8000 },
        ],
      },
      {
        group: 'wants', name: 'Wants', target_cents: 156000, actual_cents: 3245,
        categories: [{ id: 7, name: 'Eating out', target_cents: 30000, actual_cents: 3245 }],
      },
      {
        group: 'savings', name: 'Savings', target_cents: 104000, actual_cents: 10000,
        categories: [{ id: 12, name: 'Emergency fund', target_cents: 50000, actual_cents: 10000 }],
      },
    ],
  },
  transactions: [
    { id: 981, date: '2026-10-02', description: 'Corner Cafe', amount_cents: -3245, category_id: 7, account_id: 1 },
    { id: 975, date: '2026-10-01', description: 'Paycheck', amount_cents: 260000, category_id: null, account_id: 1 },
  ],
  accounts: [
    { id: 1, name: 'Everyday checking', kind: 'checking', balance_cents: 342150, balance_as_of: '2026-10-02' },
    { id: 2, name: 'Rainy day', kind: 'savings', balance_cents: 1250000, balance_as_of: '2026-09-30' },
  ],
  tax: {
    year: 2026,
    donations_total_cents: 45000,
    realized_gains: { short_term_cents: -12000, long_term_cents: 84000, is_estimate: true },
    deductions: [{ kind: 'medical', label: 'Medical', amount_cents: 23000, is_estimate: false }],
    disclaimer: "These totals help you get ready for tax time. They aren't tax advice.",
  },
  settings: { reminder_days_default: 2, reminder_days_allowed: [1, 2, 3] },
};

/** Deep copy of the sample, edited by `mutate`. */
function broken(mutate: (s: any) => void): unknown {
  const copy = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
  mutate(copy);
  return copy;
}

function expectRejected(input: unknown, detailsContains?: string) {
  const result = parseSnapshot(input);
  expect(result.ok).toBe(false);
  if (!result.ok) {
    expect(result.message).toBe(SNAPSHOT_INVALID_MESSAGE);
    if (detailsContains) expect(result.details).toContain(detailsContains);
  }
}

describe('parseSnapshot', () => {
  it('accepts the sample snapshot unchanged', () => {
    const result = parseSnapshot(SAMPLE_SNAPSHOT);
    expect(result).toEqual({ ok: true, snapshot: SAMPLE_SNAPSHOT });
  });

  it('accepts the sample after a JSON round trip (as it comes from storage)', () => {
    expect(isSnapshot(JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT)))).toBe(true);
  });

  it('accepts the example from the sync contract', () => {
    expect(parseSnapshot(CONTRACT_EXAMPLE).ok).toBe(true);
  });

  it('accepts an empty-database snapshot (zeros, empty lists, three empty groups)', () => {
    const empty = broken((s) => {
      s.income = { expected_cents: 0, received_cents: 0, last_paycheck: null };
      s.budget = {
        target_cents: 0,
        actual_cents: 0,
        groups: ['needs', 'wants', 'savings'].map((g) => ({
          group: g, name: g, target_cents: 0, actual_cents: 0, categories: [],
        })),
      };
      s.transactions = [];
      s.accounts = [];
      s.tax.deductions = [];
    });
    expect(parseSnapshot(empty).ok).toBe(true);
  });

  it('ignores unknown extra fields and drops them from the result', () => {
    const extra = broken((s) => {
      s.new_feature = { anything: true };
      s.budget.groups[0].color = 'blue';
    });
    const result = parseSnapshot(extra);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.snapshot).toEqual(SAMPLE_SNAPSHOT);
    }
  });

  it.each([
    ['null', null],
    ['a string', 'hello'],
    ['an array', []],
    ['an empty object', {}],
  ])('rejects %s', (_label, input) => {
    expectRejected(input);
  });

  it('asks for an update when the contract version is newer', () => {
    const result = parseSnapshot(broken((s) => (s.contract = 2)));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toBe(SNAPSHOT_UPDATE_MESSAGE);
  });

  it('rejects money as a float or a string', () => {
    expectRejected(broken((s) => (s.income.received_cents = 12.5)), 'income.received_cents');
    expectRejected(broken((s) => (s.budget.groups[1].actual_cents = '100')), 'budget.groups[1].actual_cents');
    expectRejected(broken((s) => (s.transactions[0].amount_cents = Number.NaN)), 'transactions[0].amount_cents');
  });

  it('rejects missing sections', () => {
    expectRejected(broken((s) => delete s.tax), 'tax');
    expectRejected(broken((s) => delete s.budget.groups), 'budget.groups');
    expectRejected(broken((s) => delete s.settings), 'settings');
  });

  it('rejects a missing or duplicated group', () => {
    expectRejected(broken((s) => s.budget.groups.pop()), 'savings');
    expectRejected(broken((s) => (s.budget.groups[1].group = 'needs')), 'needs');
    expectRejected(broken((s) => (s.budget.groups[0].group = 'fun')), 'budget.groups[0].group');
  });

  it('rejects badly formatted dates and months', () => {
    expectRejected(broken((s) => (s.transactions[2].date = '10/16/2026')), 'transactions[2].date');
    expectRejected(broken((s) => (s.period.month = 'October')), 'period.month');
    expectRejected(broken((s) => (s.generated_at = 'yesterday')), 'generated_at');
  });

  it('skips an account with a kind this phone does not know yet (contract 7.1)', () => {
    const result = parseSnapshot(broken((s) => (s.accounts[0].kind = 'credit_card')));
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.snapshot.accounts).toEqual(SAMPLE_SNAPSHOT.accounts.slice(1));
    }
  });

  it('rejects a missing account kind and bad reminder settings', () => {
    expectRejected(broken((s) => (s.accounts[0].kind = 42)), 'accounts[0].kind');
    expectRejected(broken((s) => (s.settings.reminder_days_default = 7)), 'reminder_days_default');
  });

  it('rejects impossible period numbers', () => {
    expectRejected(broken((s) => (s.period.days_in_month = 40)), 'days_in_month');
    expectRejected(broken((s) => (s.period.days_elapsed = 32)), 'days_elapsed');
  });

  it('never throws, even on odd input', () => {
    const cyclic: any = { contract: 1 };
    cyclic.period = cyclic;
    expect(() => parseSnapshot(cyclic)).not.toThrow();
    expect(parseSnapshot(cyclic).ok).toBe(false);
  });
});
