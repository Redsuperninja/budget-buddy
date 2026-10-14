// One column per month from a zero line: up (first series color) when the value is positive, down (second) when it
// isn't, with the exact amount on hover. rows: [{ label, cents }]. Drawn `width` wide (charts/fit.js); narrow
// charts label every other month.

import { formatCents, shortDollars } from "../money.js";
import { labelEvery } from "./line-chart.js";
import { linear, niceRange, ticks } from "./scale.js";
import { s } from "./svg.js";

const H = 200;
const PAD = { left: 56, right: 8, top: 10, bottom: 28 };
const GAP = 0.3; // share of each slot left empty between columns

export function columnChart(rows, description, width = 640, { up = "Kept", down = "Over" } = {}) {
  const range = niceRange(Math.min(...rows.map((r) => r.cents)), Math.max(...rows.map((r) => r.cents)), 4);
  const y = linear(range, H - PAD.bottom, PAD.top);
  const slot = (width - PAD.left - PAD.right) / Math.max(1, rows.length);
  const barW = Math.max(4, slot * (1 - GAP));
  const every = labelEvery(rows.length, width - PAD.left - PAD.right, 46);
  return s("svg", { class: "chart", viewBox: `0 0 ${width} ${H}`, width, role: "img", "aria-label": description },
    ticks(range).map((t) => s("g", {},
      s("line", { class: t === 0 ? "grid zero" : "grid", x1: PAD.left, x2: width - PAD.right, y1: y(t), y2: y(t) }),
      s("text", { x: PAD.left - 8, y: y(t) + 4, "text-anchor": "end" }, shortDollars(t)))),
    rows.map((r, i) => {
      const left = PAD.left + i * slot + (slot - barW) / 2;
      const top = Math.min(y(0), y(r.cents));
      const kept = r.cents >= 0;
      return s("g", { class: `row ${kept ? "series-1" : "series-2"}` },
        s("title", {}, `${r.label}: ${kept ? up : down} ${formatCents(Math.abs(r.cents))}`),
        s("rect", { class: "hit", x: PAD.left + i * slot, y: PAD.top, width: slot, height: H - PAD.top - PAD.bottom }),
        r.cents ? s("rect", { class: "bar", x: left, y: top, width: barW, height: Math.max(2, Math.abs(y(r.cents) - y(0))),
          rx: Math.min(4, barW / 2) }) : null,
        (rows.length - 1 - i) % every === 0
          ? s("text", { x: left + barW / 2, y: H - 8, "text-anchor": "middle" }, r.label) : null);
    }));
}
