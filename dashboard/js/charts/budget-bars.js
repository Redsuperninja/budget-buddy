// Spent against budget: one bar per row for what was spent, and a short dark line where the budget is.
// rows: [{ label, actual, budget, href? }] in cents. Hovering a row shows the exact amounts; with href, clicking it
// opens that page (left out of the Tab order: the same links are in the chart's table, for keyboards and screen readers).

import { formatCents, shortDollars } from "../money.js";
import { percentUsed } from "../percent.js";
import { linear, niceRange, ticks } from "./scale.js";
import { s } from "./svg.js";

const WIDTH = 640;
const ROW = 34;
const BAR_X = 150;
const BAR_END = 520;
const AXIS = 22;

function rowTitle({ label, actual, budget }) {
  const used = percentUsed(actual, budget);
  const plan = budget > 0 ? ` of a ${formatCents(budget)} budget${used === null ? "" : ` (${used}%)`}` : " (no budget)";
  return `${label}: ${formatCents(actual)} spent${plan}`;
}

function row(r, i, x) {
  const top = i * ROW;
  const spent = Math.max(0, r.actual);
  const over = r.budget > 0 && r.actual > r.budget;
  const value = `${shortDollars(spent)}${r.budget > 0 ? ` of ${shortDollars(r.budget)}` : ""}${over ? " (over)" : ""}`;
  const g = s("g", { class: r.href ? "row linked" : "row" },
    s("title", {}, rowTitle(r)),
    s("rect", { class: "hit", x: 0, y: top, width: WIDTH, height: ROW }),
    s("text", { class: "label", x: 0, y: top + 21 }, r.label),
    spent > 0 ? s("rect", { class: "bar", x: BAR_X, y: top + 10, width: x(spent) - BAR_X, height: 14, rx: 3 }) : null,
    r.budget > 0 ? s("line", { class: "budget-mark", x1: x(r.budget), x2: x(r.budget), y1: top + 5, y2: top + 29 }) : null,
    s("text", { x: BAR_END + 10, y: top + 21 }, value));
  return r.href ? s("a", { href: r.href, tabindex: "-1" }, g) : g;
}

export function budgetBars(rows, description) {
  const range = niceRange(0, Math.max(0, ...rows.flatMap((r) => [r.actual, r.budget])), 4);
  const x = linear(range, BAR_X, BAR_END);
  const height = rows.length * ROW + AXIS;
  const grid = ticks(range).map((t) => s("g", {},
    s("line", { class: "grid", x1: x(t), x2: x(t), y1: 0, y2: height - AXIS }),
    s("text", { x: x(t), y: height - 6, "text-anchor": "middle" }, shortDollars(t))));
  return s("svg", { class: "chart series-1", viewBox: `0 0 ${WIDTH} ${height}`, role: "img", "aria-label": description },
    grid, rows.map((r, i) => row(r, i, x)));
}
