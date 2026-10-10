// Spending pace: what you'd spent by each day of the month (a line that stops at today), against a dashed line
// for spending the month's budget evenly. Hovering shows each day's numbers. pace: the server's SpendingPace.
// Drawn `width` wide (charts/fit.js).

import { formatCents, shortDollars } from "../money.js";
import { hoverGuide } from "./hover.js";
import { evenPace } from "./pace.js";
import { linear, niceRange, ticks } from "./scale.js";
import { s } from "./svg.js";

const H = 220;
const PAD = { left: 56, right: 70, top: 12, bottom: 28 };
const DAY_TICKS = [1, 8, 15, 22];

export function paceChart(pace, description, width = 640) {
  const days = pace.days_in_month;
  const spent = pace.days.map((d) => d.spent_cents);
  const range = niceRange(Math.min(0, ...spent), Math.max(pace.budget_cents, ...spent), 4);
  const y = linear(range, H - PAD.bottom, PAD.top);
  const right = width - PAD.right;
  const x = (i) => PAD.left + (days > 1 ? (i * (right - PAD.left)) / (days - 1) : 0); // i: day - 1
  const last = spent.length - 1;
  const hover = spent.length ? hoverGuide({
    count: spent.length, x, top: PAD.top, bottom: H - PAD.bottom, width,
    texts: (i) => [`Day ${i + 1}`, `Spent so far: ${formatCents(spent[i])}`,
      `Even pace: ${formatCents(evenPace(pace.budget_cents, i + 1, days))}`],
  }) : null;
  return s("svg", { class: "chart", viewBox: `0 0 ${width} ${H}`, width, role: "img", "aria-label": description },
    ticks(range).map((t) => s("g", {},
      s("line", { class: t === 0 ? "grid zero" : "grid", x1: PAD.left, x2: right, y1: y(t), y2: y(t) }),
      s("text", { x: PAD.left - 8, y: y(t) + 4, "text-anchor": "end" }, shortDollars(t)))),
    DAY_TICKS.filter((d) => d <= days).map((d) => s("text", { x: x(d - 1), y: H - 8, "text-anchor": "middle" }, `${d}`)),
    pace.budget_cents > 0 ? s("g", { class: "pace-budget" },
      s("line", { class: "guide", x1: x(0), y1: y(evenPace(pace.budget_cents, 1, days)), x2: x(days - 1),
        y2: y(pace.budget_cents) }),
      s("text", { class: "label", x: right + 6, y: y(pace.budget_cents) + 4 }, "Budget")) : null,
    spent.length ? s("g", { class: "series-1" },
      s("path", { class: "area", d: `M${x(0)},${y(0)}L${spent.map((v, i) => `${x(i)},${y(v)}`).join("L")}` +
        `L${x(last)},${y(0)}Z` }),
      s("path", { class: "line", d: `M${spent.map((v, i) => `${x(i)},${y(v)}`).join("L")}` }),
      s("circle", { class: "dot", cx: x(last), cy: y(spent[last]), r: 4 }),
      s("text", { class: "label", x: x(last) + 8, y: y(spent[last]) - 8 }, shortDollars(spent[last]))) : null,
    hover);
}
