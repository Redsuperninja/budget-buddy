// Axis maths for the charts: a range with round steps that always includes zero, and turning values
// into positions. (Positions only: money itself stays whole cents everywhere else.)

// The smallest of 1, 2, 2.5, 5 or 10 (times a power of ten) that fits `span` in about `count` steps.
export function niceStep(span, count = 4) {
  const raw = span / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 2.5, 5, 10].map((f) => f * magnitude).find((step) => step >= raw);
}

// { lo, hi, step } covering min..max and zero, with round ends.
export function niceRange(min, max, count = 4) {
  const lo = Math.min(0, min);
  const hi = Math.max(0, max, lo + 1);
  const step = niceStep(hi - lo, count);
  return { lo: Math.floor(lo / step) * step, hi: Math.ceil(hi / step) * step, step };
}

export function ticks({ lo, hi, step }) {
  const out = [];
  for (let v = lo; v <= hi + step / 2; v += step) out.push(Math.round(v));
  return out;
}

// A function from a value in lo..hi to a position in from..to.
export const linear = ({ lo, hi }, from, to) => (value) => from + ((value - lo) * (to - from)) / (hi - lo);
