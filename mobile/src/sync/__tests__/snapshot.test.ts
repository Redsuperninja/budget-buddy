import { SAMPLE_SNAPSHOT } from '../sampleSnapshot';
import {
  isSnapshot,
  parseSnapshot,
  SNAPSHOT_INVALID_MESSAGE,
  SNAPSHOT_UPDATE_MESSAGE,
} from '../snapshot';

// Jest runs in Node; the app's tsconfig leaves Node's types out, so name the two globals used here.
declare const require: (name: string) => any;
declare const __dirname: string;

/** The example from docs/api/sync-contract/05-snapshot.md §5.2, read from the doc itself. The server's
 * tests read the same block (server/tests/contract_example.py), so all three stay in step. */
function contractExample(): unknown {
  const { readFileSync } = require('fs');
  const { join } = require('path');
  const doc = join(__dirname, '..', '..', '..', '..', 'docs', 'api', 'sync-contract', '05-snapshot.md');
  const blocks = [...readFileSync(doc, 'utf8').matchAll(/```json\r?\n([\s\S]*?)```/g)];
  expect(blocks).toHaveLength(1);
  return JSON.parse(blocks[0][1]);
}

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
    expect(parseSnapshot(contractExample()).ok).toBe(true);
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

  it('counts accounts of a kind this app version does not know, and keeps the count when re-read', () => {
    const future = (count: number) =>
      broken((s) => {
        for (let i = 0; i < count; i++) {
          s.accounts.push({ ...s.accounts[0], id: 900 + i, kind: 'crypto_wallet' });
        }
      });
    const none = parseSnapshot(broken(() => {}));
    expect(none.ok && none.snapshot.skipped_accounts).toBeUndefined();
    for (const count of [1, 3]) {
      const result = parseSnapshot(future(count));
      expect(result.ok).toBe(true);
      if (!result.ok) continue;
      expect(result.snapshot.accounts).toHaveLength(SAMPLE_SNAPSHOT.accounts.length);
      expect(result.snapshot.skipped_accounts).toBe(count);
      // The phone saves the checked copy and checks it again on start.
      const again = parseSnapshot(JSON.parse(JSON.stringify(result.snapshot)));
      expect(again.ok && again.snapshot.skipped_accounts).toBe(count);
    }
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

  it('accepts every account kind in the contract', () => {
    const kinds = ['checking', 'savings', 'brokerage', 'credit_card', 'cash', 'loan', 'retirement', 'hsa', 'other'];
    const result = parseSnapshot(broken((s) => (s.accounts = kinds.map((kind, i) => ({ ...s.accounts[0], id: i, kind })))));
    expect(result.ok && result.snapshot.accounts.map((a) => a.kind)).toEqual(kinds);
  });

  it('skips an account with a kind this phone does not know yet (contract 7.1)', () => {
    const result = parseSnapshot(broken((s) => (s.accounts[0].kind = 'crypto_wallet')));
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.snapshot.accounts).toEqual(SAMPLE_SNAPSHOT.accounts.slice(1));
    }
  });

  it('keeps budget.unassigned when present and allows it to be absent', () => {
    const withIt = parseSnapshot(broken(() => {}));
    expect(withIt.ok && withIt.snapshot.budget.unassigned).toEqual({ in_cents: 0, out_cents: 4599, count: 2 });
    const without = parseSnapshot(broken((s) => delete s.budget.unassigned));
    expect(without.ok && 'unassigned' in without.snapshot.budget).toBe(false);
  });

  it('rejects a bad budget.unassigned', () => {
    expectRejected(broken((s) => (s.budget.unassigned.count = -1)), 'budget.unassigned.count');
    expectRejected(broken((s) => (s.budget.unassigned.out_cents = 1.5)), 'budget.unassigned.out_cents');
    expectRejected(broken((s) => (s.budget.unassigned = 'many')), 'budget.unassigned');
  });

  it('rejects a missing account kind and bad reminder settings', () => {
    expectRejected(broken((s) => (s.accounts[0].kind = 42)), 'accounts[0].kind');
    expectRejected(broken((s) => (s.settings.reminder_days_default = 7)), 'reminder_days_default');
  });

  it('rejects impossible period numbers', () => {
    expectRejected(broken((s) => (s.period.days_in_month = 40)), 'days_in_month');
    expectRejected(broken((s) => (s.period.days_elapsed = 32)), 'days_elapsed');
  });

  const periodOf = (month: string, days: number, elapsed = 1) => ({
    month, start: `${month}-01`, end: `${month}-${days}`, days_elapsed: elapsed, days_in_month: days,
  });

  it.each([
    ['February 2027', periodOf('2027-02', 28)],
    ['February 2028 (a leap year)', periodOf('2028-02', 29, 29)],
    ['December', periodOf('2026-12', 31, 31)],
  ])('accepts a consistent month: %s', (_name, period) => {
    expect(parseSnapshot(broken((s) => (s.period = period))).ok).toBe(true);
  });

  it.each([
    ['February 2027 said to have 29 days', { ...periodOf('2027-02', 28), days_in_month: 29, end: '2027-02-29' }, 'days_in_month'],
    ['start not the 1st', { ...periodOf('2026-10', 31), start: '2026-10-02' }, 'period.start'],
    ['end not the last day', { ...periodOf('2026-10', 31), end: '2026-10-30' }, 'period.end'],
    ['end in another month', { ...periodOf('2026-10', 31), end: '2026-11-30' }, 'period.end'],
    ['no days elapsed (today counts)', periodOf('2026-10', 31, 0), 'days_elapsed'],
    ['month 13', { ...periodOf('2026-10', 31), month: '2026-13' }, 'period.month'],
  ])('rejects a month that does not add up: %s', (_name, period, field) => {
    expectRejected(broken((s) => (s.period = period)), field);
  });

  it('never throws, even on odd input', () => {
    const cyclic: any = { contract: 1 };
    cyclic.period = cyclic;
    expect(() => parseSnapshot(cyclic)).not.toThrow();
    expect(parseSnapshot(cyclic).ok).toBe(false);
  });
});
