import { accountKindLabel, formatAccountBalance, unassignedNote } from '../accounts';

describe('formatAccountBalance', () => {
  it.each([
    ['credit_card', -5000, '$50.00 owed'],
    ['loan', -1234567, '$12,345.67 owed'],
    ['credit_card', 1200, '$12.00 credit'],
    ['credit_card', 0, '$0.00'],
    ['checking', 342150, '$3,421.50'],
    ['checking', -500, '-$5.00'],
  ] as const)('%s %i -> %s', (kind, cents, text) => {
    expect(formatAccountBalance({ kind, balance_cents: cents })).toBe(text);
  });
});

describe('labels and notes', () => {
  it('has plain-English kind labels', () => {
    expect(accountKindLabel('credit_card')).toBe('Credit card');
    expect(accountKindLabel('brokerage')).toBe('Investments');
  });

  it('words the unassigned note, and says nothing when there are none', () => {
    expect(unassignedNote(undefined)).toBeNull();
    expect(unassignedNote(0)).toBeNull();
    expect(unassignedNote(1)).toBe('1 transaction needs a category on your computer.');
    expect(unassignedNote(3)).toBe('3 transactions need a category on your computer.');
  });
});
