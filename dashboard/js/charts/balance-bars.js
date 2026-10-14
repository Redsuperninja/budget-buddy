// What you have and what you owe: one bar per account from a center line, right for money you have, left for money
// owed (credit cards, loans, overdrawn accounts). rows: [{ label, cents }] with owed money negative. Hovering a
// row shows the exact balance. Drawn `width` wide (charts/fit.js).

import { formatCents, shortDollars } from "../money.js";
import { clip } from "./fit.js";
import { signedExtent } from "./shares.js";
import { s } from "./svg.js";

const ROW = 30;
const AMOUNT_W = 56; // room for the amount past the end of a bar

export function balanceBars(rows, description, width = 640) {
  const labelW = Math.min(170, Math.round(width * 0.3));
  const mid = labelW + (width - labelW) / 2;
  const half = (width - labelW) / 2 - AMOUNT_W;
  const extent = signedExtent(rows.map((r) => r.cents));
  const length = (cents) => (Math.abs(cents) / extent) * half;
  const height = rows.length * ROW + 4;
  return s("svg", { class: "chart", viewBox: `0 0 ${width} ${height}`, width, role: "img", "aria-label": description },
    s("line", { class: "grid zero", x1: mid, x2: mid, y1: 0, y2: height }),
    rows.map((r, i) => {
      const top = i * ROW;
      const owed = r.cents < 0;
      const end = owed ? mid - length(r.cents) : mid + length(r.cents);
      return s("g", { class: `row ${owed ? "series-2" : "series-1"}` },
        s("title", {}, `${r.label}: ${owed ? `${formatCents(-r.cents)} owed` : formatCents(r.cents)}`),
        s("rect", { class: "hit", x: 0, y: top, width, height: ROW }),
        s("text", { class: "label", x: 0, y: top + 19 }, clip(r.label, labelW - 8)),
        r.cents ? s("rect", { class: "bar", x: Math.min(mid, end), y: top + 9, width: Math.max(2, Math.abs(end - mid)),
          height: 12, rx: 4 }) : null,
        s("text", { x: owed ? end - 6 : end + 6, y: top + 19, "text-anchor": owed ? "end" : "start" },
          owed ? `-${shortDollars(-r.cents)}` : shortDollars(r.cents)));
    }));
}
