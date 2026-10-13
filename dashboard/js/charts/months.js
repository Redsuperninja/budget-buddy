// Chart maths across months: the trend from the first month with any money in it, the points of a small trend line,
// which days of last month to compare with, and how spending in each category changed. Pure, so it's tested.

const pad = (n) => String(n).padStart(2, "0");
const daysIn = (year, month) => new Date(year, month, 0).getDate();

// Whether a month (a trend month or a monthly summary) has any money in it, sorted or not.
export const hasMoney = (m) =>
  Boolean(m.income_cents || m.spending_cents || m.saved_cents || m.unassigned_in_cents || m.unassigned_out_cents);

// months: the trend API's months, oldest first. Leading months with nothing in them are dropped (a new user's year
// isn't eleven flat months); a year with nothing at all is kept as it is.
export function fromFirstActivity(months) {
  const first = months.findIndex(hasMoney);
  return first === -1 ? months : months.slice(first);
}

// "x,y x,y ..." for an SVG polyline width x height, the highest value at the top. One value draws a flat line.
export function sparkPoints(values, width, height) {
  const lo = Math.min(...values);
  const span = Math.max(...values) - lo || 1;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  const y = (v) => height - ((v - lo) / span) * height;
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${y(v).toFixed(1)}`);
  return values.length === 1 ? `${points[0]} ${width},${y(values[0]).toFixed(1)}` : points.join(" ");
}

// The month before `month`, and, when `month` is the one `today` is in, the days to compare: this month so far
// against the same days of last month (cut short when last month had fewer days). Past months compare whole.
export function comparedWith(month, today) {
  const [year, m] = month.split("-").map(Number);
  const [prevYear, prevM] = m === 1 ? [year - 1, 12] : [year, m - 1];
  const previous = `${prevYear}-${pad(prevM)}`;
  if (today.slice(0, 7) !== month) return { previous, through: null, previousThrough: null };
  const day = Math.min(Number(today.slice(8, 10)), daysIn(prevYear, prevM));
  return { previous, through: today, previousThrough: `${previous}-${pad(day)}` };
}

// The day of a "YYYY-MM-DD" date in words: "1st", "2nd", "13th", "22nd".
export function dayOfMonth(date) {
  const n = Number(date.slice(8, 10));
  const end = n >= 11 && n <= 13 ? "th" : { 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th";
  return `${n}${end}`;
}

const SPENDING = new Set(["needs", "wants"]);

// How each spending category changed from `previous` to `current` (monthly summaries): [{ label, cents }], more
// spent positive, biggest changes first. Past `limit` the rest add up into one "Everything else" row.
export function spendingChanges(current, previous, limit = 7) {
  const before = new Map(previous.categories.map((c) => [c.category_id, c.actual_cents]));
  const rows = current.categories
    .filter((c) => SPENDING.has(c.group))
    .map((c) => ({ label: c.name, cents: c.actual_cents - (before.get(c.category_id) || 0) }))
    .filter((r) => r.cents !== 0)
    .sort((a, b) => Math.abs(b.cents) - Math.abs(a.cents) || a.label.localeCompare(b.label));
  if (rows.length <= limit) return rows;
  const rest = rows.slice(limit - 1).reduce((sum, r) => sum + r.cents, 0);
  return [...rows.slice(0, limit - 1), ...(rest ? [{ label: "Everything else", cents: rest }] : [])];
}
