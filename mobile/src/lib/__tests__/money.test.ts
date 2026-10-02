import { formatCents } from '../money';

describe('formatCents', () => {
  it('formats zero', () => {
    expect(formatCents(0)).toBe('$0.00');
  });

  it('formats small amounts with leading zero cents', () => {
    expect(formatCents(1)).toBe('$0.01');
    expect(formatCents(5)).toBe('$0.05');
    expect(formatCents(99)).toBe('$0.99');
  });

  it('formats whole dollars and cents', () => {
    expect(formatCents(100)).toBe('$1.00');
    expect(formatCents(123456)).toBe('$1,234.56');
  });

  it('formats negatives with a leading minus', () => {
    expect(formatCents(-500)).toBe('-$5.00');
    expect(formatCents(-1)).toBe('-$0.01');
    expect(formatCents(-123456789)).toBe('-$1,234,567.89');
  });

  it('does not show negative zero', () => {
    expect(formatCents(-0)).toBe('$0.00');
  });

  it('formats large numbers exactly', () => {
    expect(formatCents(100_000_000_00)).toBe('$100,000,000.00');
    // Largest safe integer: no floating-point drift in the cents.
    expect(formatCents(Number.MAX_SAFE_INTEGER)).toBe('$90,071,992,547,409.91');
  });

  it('rounds fractional cents to the nearest cent', () => {
    expect(formatCents(199.6)).toBe('$2.00');
  });

  it('accepts other currencies', () => {
    expect(formatCents(250, 'EUR')).toBe('€2.50');
  });

  it('rejects non-finite values', () => {
    expect(() => formatCents(Number.NaN)).toThrow(RangeError);
    expect(() => formatCents(Number.POSITIVE_INFINITY)).toThrow(RangeError);
  });
});
