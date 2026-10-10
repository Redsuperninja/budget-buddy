// Where the month's income went: one bar the length of the income, split into needs, wants and savings (the
// series colors), with what's left over in gray. If more went out than came in, the bar is longer and a line
// marks where the income ran out. Each part is labeled under the bar; hovering shows the exact amount. Drawn
// `width` wide (charts/fit.js).

import { formatCents } from "../money.js";
import { incomeSplit } from "./shares.js";
import { s } from "./svg.js";

const BAR_Y = 8;
const BAR_H = 28;
const GAP = 2; // a thin gap between parts, so touching colors stay apart
const LABEL_PX = 64; // parts narrower than this are named in the hover only

// parts: [{ name, cents }] in series order (series-1, -2, -3).
export function incomeSplitChart(income, parts, description, width = 640) {
  const split = incomeSplit(income, parts);
  const x = (share) => share * width;
  const pieces = split.segments.map((p, i) => ({ ...p, cls: `series-${i + 1}` }));
  if (split.leftover > 0 && split.total > 0) {
    pieces.push({ name: "Left over", cents: split.leftover, cls: "leftover",
      start: 1 - split.leftover / split.total, size: split.leftover / split.total,
      percent: Math.round((split.leftover * 100) / income) });
  }
  const shown = pieces.filter((p) => p.size > 0);
  const tip = (p) => `${p.name}: ${formatCents(p.cents)}${p.percent === null ? "" : ` (${p.percent}% of income)`}`;
  return s("svg", { class: "chart", viewBox: `0 0 ${width} 80`, width, role: "img", "aria-label": description },
    shown.map((p, i) => {
      const named = x(p.size) >= LABEL_PX;
      return s("g", { class: `row ${p.cls}` },
        s("title", {}, tip(p)),
        s("rect", { class: "bar", x: x(p.start) + (i ? GAP / 2 : 0), y: BAR_Y,
          width: Math.max(1, x(p.size) - (i ? GAP / 2 : 0) - (i < shown.length - 1 ? GAP / 2 : 0)), height: BAR_H,
          rx: 6 }),
        named ? s("text", { class: "label", x: x(p.start) + 4, y: BAR_Y + BAR_H + 18 }, p.name) : null,
        named && p.percent !== null ? s("text", { x: x(p.start) + 4, y: BAR_Y + BAR_H + 34 }, `${p.percent}%`) : null);
    }),
    split.over ? s("g", {},
      s("title", {}, `Income ran out here: ${formatCents(-split.leftover)} more went out than came in`),
      s("line", { class: "budget-mark", x1: x(income / split.total), x2: x(income / split.total), y1: 2,
        y2: BAR_Y + BAR_H + 6 })) : null);
}
