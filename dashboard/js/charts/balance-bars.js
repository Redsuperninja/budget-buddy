// What you have and what you owe: one bar per account from a center line, right for money you have, left for money
// owed (credit cards, loans, overdrawn accounts). rows: [{ label, cents }] with owed money negative. Hovering a
// row shows the exact balance.

import { formatCents, shortDollars } from "../money.js";
import { signedExtent } from "./shares.js";
import { s } from "./svg.js";

const WIDTH = 640;
const ROW = 30;
const LABEL_W = 170;
const MID = LABEL_W + (WIDTH - LABEL_W) / 2;
const HALF = (WIDTH - LABEL_W) / 2 - 60; // room for the amount past the end of the bar

export function balanceBars(rows, description) {
  const extent = signedExtent(rows.map((r) => r.cents));
  const length = (cents) => (Math.abs(cents) / extent) * HALF;
  const height = rows.length * ROW + 4;
  return s("svg", { class: "chart", viewBox: `0 0 ${WIDTH} ${height}`, role: "img", "aria-label": description },
    s("line", { class: "grid zero", x1: MID, x2: MID, y1: 0, y2: height }),
    rows.map((r, i) => {
      const top = i * ROW;
      const owed = r.cents < 0;
      const end = owed ? MID - length(r.cents) : MID + length(r.cents);
      return s("g", { class: `row ${owed ? "series-2" : "series-1"}` },
        s("title", {}, `${r.label}: ${owed ? `${formatCents(-r.cents)} owed` : formatCents(r.cents)}`),
        s("rect", { class: "hit", x: 0, y: top, width: WIDTH, height: ROW }),
        s("text", { class: "label", x: 0, y: top + 19 }, r.label),
        r.cents ? s("rect", { class: "bar", x: Math.min(MID, end), y: top + 8, width: Math.max(1, Math.abs(end - MID)),
          height: 14, rx: 3 }) : null,
        s("text", { x: owed ? end - 6 : end + 6, y: top + 19, "text-anchor": owed ? "end" : "start" },
          owed ? `-${shortDollars(-r.cents)}` : shortDollars(r.cents)));
    }));
}
