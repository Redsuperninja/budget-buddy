/**
 * Money arrives from the Home Base as integer cents. Only format it at display time.
 */

/**
 * Format integer cents as a currency string (en-US style), e.g.
 *   123456 -> "$1,234.56", -500 -> "-$5.00", 0 -> "$0.00".
 *
 * Dollars and cents are split with integer math so large amounts never pick up
 * floating-point rounding errors. Assumes a currency with 2 decimal places (USD, EUR, CAD...).
 * Non-integer input is rounded to the nearest cent.
 */
export function formatCents(cents: number, currency = 'USD'): string {
  if (!Number.isFinite(cents)) {
    throw new RangeError(`formatCents expects a finite number of cents, got ${cents}`);
  }
  const rounded = Math.round(cents);
  const negative = rounded < 0;
  const abs = Math.abs(rounded);
  const whole = Math.floor(abs / 100);
  const fraction = abs % 100;

  const dollars = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(whole);

  return `${negative ? '-' : ''}${dollars}.${fraction.toString().padStart(2, '0')}`;
}

/**
 * Typed dollars to whole cents with string logic only (no float maths): "12.34", "$1,234.5", ".50" and
 * "12." all work. Returns null for anything else, a negative amount, or more than 2 decimal places.
 */
export function parseDollars(text: string): number | null {
  const t = text.trim().replace(/^\$/, '').replace(/,/g, '');
  if (!/^(\d+\.?\d*|\.\d+)$/.test(t)) return null;
  const [whole, fraction = ''] = t.split('.');
  if (fraction.length > 2 || whole.length > 9) return null;
  return Number(whole || '0') * 100 + Number((fraction + '00').slice(0, 2));
}
