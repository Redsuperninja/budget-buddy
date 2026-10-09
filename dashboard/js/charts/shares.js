// Chart maths for parts of a whole: how a month's income was split into needs, wants and savings, and how
// long each bar is when some values are negative (money owed).

// income and parts' cents are whole cents. The bar is as long as the larger of income and everything spent or
// saved, so spending more than came in still fits and shows by how much.
// Returns { total, segments: [{ ...part, start, size, percent }], leftover, over } where start and size are
// shares of the bar (0 to 1), percent is the share of income (null with no income), leftover is income minus
// the parts (negative when more went out than came in), and over says whether it did.
export function incomeSplit(income, parts) {
  const positive = parts.map((p) => ({ ...p, cents: Math.max(0, p.cents) }));
  const used = positive.reduce((sum, p) => sum + p.cents, 0);
  const total = Math.max(income, used, 0);
  let start = 0;
  const segments = positive.map((p) => {
    const size = total > 0 ? p.cents / total : 0;
    const segment = { ...p, start, size, percent: percentOf(p.cents, income) };
    start += size;
    return segment;
  });
  const leftover = income - used;
  return { total, segments, leftover, over: leftover < 0 };
}

// A whole-number percentage of income, or null when there's no income to compare with.
export function percentOf(cents, income) {
  return income > 0 ? Math.round((cents * 100) / income) : null;
}

// For bars that can go either way (balances): the largest size either side of zero, so both sides share a scale.
export function signedExtent(values) {
  return Math.max(1, ...values.map((v) => Math.abs(v)));
}
