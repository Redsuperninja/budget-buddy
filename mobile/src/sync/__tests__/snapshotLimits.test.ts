/** Size limits on snapshots (issue #20): lists, text, real dates, the saved copy. Made-up data only. */
import AsyncStorage from '@react-native-async-storage/async-storage';

import { SAMPLE_SNAPSHOT } from '../sampleSnapshot';
import { parseSnapshot, SNAPSHOT_INVALID_MESSAGE, SNAPSHOT_LIMITS } from '../snapshot';
import { loadStoredSnapshot, SNAPSHOT_STORAGE_KEY } from '../store';

function edited(mutate: (s: any) => void): unknown {
  const copy = JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT));
  mutate(copy);
  return copy;
}

function refusedAt(input: unknown): string | null {
  const result = parseSnapshot(input);
  return result.ok ? null : result.details;
}

describe('snapshot size limits', () => {
  it('takes 500 transactions but not 501', () => {
    const many = (n: number) => edited((s) => {
      s.transactions = Array.from({ length: n }, (_, i) => ({ ...s.transactions[0], id: i + 1 }));
    });
    expect(parseSnapshot(many(500)).ok).toBe(true);
    expect(refusedAt(many(501))).toContain('transactions');
  });

  it('takes a 100-character description but not 101', () => {
    const described = (n: number) => edited((s) => (s.transactions[0].description = 'x'.repeat(n)));
    expect(parseSnapshot(described(100)).ok).toBe(true);
    expect(refusedAt(described(101))).toContain('transactions[0].description');
    // 100 emoji are 100 characters to the Home Base (and 200 code units in JavaScript).
    const emoji = edited((s) => (s.transactions[0].description = '\u{1F600}'.repeat(100)));
    expect(parseSnapshot(emoji).ok).toBe(true);
  });

  it('caps accounts, categories, deductions, names and the disclaimer, accepting the limit itself', () => {
    const accounts = (n: number) => edited((s) => (s.accounts = Array(n).fill(s.accounts[0])));
    expect(parseSnapshot(accounts(1000)).ok).toBe(true);
    expect(refusedAt(accounts(1001))).toContain('accounts');
    const categories = (n: number) =>
      edited((s) => (s.budget.groups[0].categories = Array(n).fill(s.budget.groups[0].categories[0])));
    expect(parseSnapshot(categories(1000)).ok).toBe(true);
    expect(refusedAt(categories(1001))).toContain('categories');
    const deductions = (n: number) => edited((s) => (s.tax.deductions = Array(n).fill({ kind: 'x', label: 'x', amount_cents: 1, is_estimate: false })));
    expect(parseSnapshot(deductions(50)).ok).toBe(true);
    expect(refusedAt(deductions(51))).toContain('deductions');
    expect(refusedAt(edited((s) => (s.accounts[0].name = 'n'.repeat(101))))).toContain('accounts[0].name');
    expect(refusedAt(edited((s) => (s.tax.disclaimer = 'd'.repeat(501))))).toContain('disclaimer');
  });

  it('wants a real date and a Home Base ID', () => {
    expect(refusedAt(edited((s) => (s.transactions[0].date = '2026-02-30')))).toContain('transactions[0].date');
    expect(refusedAt(edited((s) => (s.transactions[0].date = '2026-99-99')))).toContain('transactions[0].date');
    expect(refusedAt(edited((s) => (s.server_id = 'not an id!')))).toContain('server_id');
    expect(refusedAt(edited((s) => (s.server_id = 'a'.repeat(65))))).toContain('server_id');
  });

  it('shows control and text-direction characters as a space, like the Home Base', () => {
    const shown = (text: string) => {
      const result = parseSnapshot(edited((s) => (s.transactions[0].description = text)));
      return result.ok ? result.snapshot.transactions[0].description : null;
    };
    expect(shown('Fake\u202Eshop\u0007')).toBe('Fake shop');
    expect(shown('Fake\u200F\u2066 shop\u2028\u0085')).toBe('Fake shop');
    expect(shown('a\nb')).toBe('a b');
  });

  it('accepts a real date in any year, even before 100', () => {
    expect(parseSnapshot(edited((s) => (s.transactions[0].date = '0050-01-01'))).ok).toBe(true);
  });

  it('does not even read a saved copy that is far too big', async () => {
    await AsyncStorage.setItem(SNAPSHOT_STORAGE_KEY, 'x'.repeat(SNAPSHOT_LIMITS.storedChars + 1));
    const state = await loadStoredSnapshot();
    expect(state.isSample).toBe(true);
    expect(state.loadError).toBe(SNAPSHOT_INVALID_MESSAGE);
  });
});
