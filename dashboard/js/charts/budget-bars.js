// Spent against budget: one bar per row for what was spent, and a short upright line where the budget is. Bars
// over budget turn the "over" color. rows: [{ label, actual, budget, href? }] in cents. Hovering a row shows the exact
// amounts; with href, clicking it opens that page (left out of the Tab order: the same links are in the chart's table,
// for keyboards and screen readers). Drawn `width` wide (charts/fit.js).

import { formatCents, shortDollars } from "../money.js";
import { percentUsed } from "../percent.js";
import { clip } from "./fit.js";
import { linear, niceRange, ticks } from "./scale.js";
import { s } from "./svg.js";

const ROW = 34;
const AXIS = 22;
const VALUE_W = 150; // room for "$1.2k of $1.5k (over)" after the bars
const COMPACT_W = 96; // on a narrow chart: "$1.2k/$1.5k over"
const NARROW = 440;

function rowTitle({ label, actual, budget }) {
  const used = percentUsed(actual, budget);
  const plan = budget > 0 ? ` of a ${formatCents(budget)} budget${used === null ? "" : ` (${used}%)`}` : " (no budget)";
  return `${label}: ${formatCents(actual)} spent${plan}`;
}

function valueText(spent, budget, over, compact) {
  if (compact) return `${shortDollars(spent)}${budget > 0 ? `/${shortDollars(budget)}` : ""}${over ? " over" : ""}`;
  return `${shortDollars(spent)}${budget > 0 ? ` of ${shortDollars(budget)}` : ""}${over ? " (over)" : ""}`;
}

function row(r, i, x, { width, barX, barEnd, compact }) {
  const top = i * ROW;
  const spent = Math.max(0, r.actual);
  const over = r.budget > 0 && r.actual > r.budget;
  const value = valueText(spent, r.budget, over, compact);
  const g = s("g", { class: `row${r.href ? " linked" : ""}${over ? " over" : ""}` },
    s("title", {}, rowTitle(r)),
    s("rect", { class: "hit", x: 0, y: top, width, height: ROW }),
    s("text", { class: "label", x: 0, y: top + 21 }, clip(r.label, barX - 8)),
    s("rect", { class: "track", x: barX, y: top + 11, width: barEnd - barX, height: 12, rx: 4 }),
    spent > 0 ? s("rect", { class: "bar", x: barX, y: top + 11, width: Math.max(2, x(spent) - barX), height: 12, rx: 4 })
      : null,
    r.budget > 0 ? s("line", { class: "budget-mark", x1: x(r.budget), x2: x(r.budget), y1: top + 6, y2: top + 28 }) : null,
    s("text", { class: over ? "value over" : "value", x: barEnd + 10, y: top + 21 }, value));
  return r.href ? s("a", { href: r.href, tabindex: "-1" }, g) : g;
}

export function budgetBars(rows, description, width = 640) {
  const barX = Math.min(150, Math.round(width * 0.3));
  const compact = width < NARROW;
  const barEnd = width - (compact ? COMPACT_W : VALUE_W);
  const range = niceRange(0, Math.max(0, ...rows.flatMap((r) => [r.actual, r.budget])), 4);
  const x = linear(range, barX, barEnd);
  const height = rows.length * ROW + AXIS;
  const grid = ticks(range).map((t) => s("g", {},
    s("line", { class: "grid", x1: x(t), x2: x(t), y1: 0, y2: height - AXIS }),
    s("text", { x: x(t), y: height - 6, "text-anchor": "middle" }, shortDollars(t))));
  return s("svg", { class: "chart series-1", viewBox: `0 0 ${width} ${height}`, width, role: "img",
    "aria-label": description },
  grid, rows.map((r, i) => row(r, i, x, { width, barX, barEnd, compact })));
}
