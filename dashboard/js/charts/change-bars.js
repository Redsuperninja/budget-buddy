// How spending changed from last month: one bar per category from a center line, right for more spent, left for
// less. rows: [{ label, cents }] with less spent negative. Every bar also says "more" or "less" in words, so the
// two colors are never the only clue. Hovering a row shows the exact change.

import { formatCents, shortDollars } from "../money.js";
import { signedExtent } from "./shares.js";
import { s } from "./svg.js";

const WIDTH = 640;
const ROW = 30;
const LABEL_W = 170;
const MID = LABEL_W + (WIDTH - LABEL_W) / 2;
const HALF = (WIDTH - LABEL_W) / 2 - 80; // room for "$1.2k more" past the end of the bar

export const changeText = (cents) => `${formatCents(Math.abs(cents))} ${cents > 0 ? "more" : "less"}`;

export function changeBars(rows, description) {
  const extent = signedExtent(rows.map((r) => r.cents));
  const length = (cents) => (Math.abs(cents) / extent) * HALF;
  const height = rows.length * ROW + 4;
  return s("svg", { class: "chart", viewBox: `0 0 ${WIDTH} ${height}`, role: "img", "aria-label": description },
    s("line", { class: "grid zero", x1: MID, x2: MID, y1: 0, y2: height }),
    rows.map((r, i) => {
      const top = i * ROW;
      const less = r.cents < 0;
      const end = less ? MID - length(r.cents) : MID + length(r.cents);
      return s("g", { class: `row ${less ? "series-1" : "series-2"}` },
        s("title", {}, `${r.label}: ${changeText(r.cents)}`),
        s("rect", { class: "hit", x: 0, y: top, width: WIDTH, height: ROW }),
        s("text", { class: "label", x: 0, y: top + 19 }, r.label),
        s("rect", { class: "bar", x: Math.min(MID, end), y: top + 8, width: Math.max(1, Math.abs(end - MID)),
          height: 14, rx: 3 }),
        s("text", { x: less ? end - 6 : end + 6, y: top + 19, "text-anchor": less ? "end" : "start" },
          `${shortDollars(Math.abs(r.cents))} ${less ? "less" : "more"}`));
    }));
}
