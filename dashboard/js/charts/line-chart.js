// A line chart over months (up to three series), with names at the line ends and a hover guide.
// series: [{ name, values }] in cents, one value per label; labels: ["Jan 2026", "Feb", ...].

import { formatCents, shortDollars } from "../money.js";
import { hoverGuide } from "./hover.js";
import { linear, niceRange, ticks } from "./scale.js";
import { s } from "./svg.js";

const W = 640;
const H = 260;
const PAD = { left: 56, right: 92, top: 12, bottom: 28 };
const LABEL_GAP = 14;

// Move the end-of-line names apart so none overlap (at least `gap` apart, keeping their order).
export function spreadLabels(ys, gap = LABEL_GAP) {
  const order = ys.map((y, i) => [y, i]).sort((a, b) => a[0] - b[0]);
  const out = [...ys];
  let last = -Infinity;
  for (const [y, i] of order) {
    out[i] = Math.max(y, last + gap);
    last = out[i];
  }
  return out;
}

function axis(range, y) {
  return ticks(range).map((t) => s("g", {},
    s("line", { class: t === 0 ? "grid zero" : "grid", x1: PAD.left, x2: W - PAD.right, y1: y(t), y2: y(t) }),
    s("text", { x: PAD.left - 8, y: y(t) + 4, "text-anchor": "end" }, shortDollars(t))));
}

function seriesLine(sr, n, x, y, labelY) {
  const path = sr.values.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join("");
  return s("g", { class: `series-${n + 1}` },
    s("path", { class: "line", d: path }),
    sr.values.map((v, i) => s("circle", { class: "dot", cx: x(i), cy: y(v), r: 4 })),
    s("text", { class: "label", x: x(sr.values.length - 1) + 10, y: labelY + 4 }, sr.name));
}

export function lineChart(series, labels, description) {
  const all = series.flatMap((sr) => sr.values);
  const range = niceRange(Math.min(...all), Math.max(...all), 4);
  const y = linear(range, H - PAD.bottom, PAD.top);
  const span = W - PAD.left - PAD.right;
  const x = (i) => PAD.left + (labels.length > 1 ? (i * span) / (labels.length - 1) : 0);
  const labelYs = spreadLabels(series.map((sr) => y(sr.values[sr.values.length - 1])));
  const hover = hoverGuide({
    count: labels.length, x, top: PAD.top, bottom: H - PAD.bottom, width: W,
    texts: (i) => [labels[i], ...series.map((sr) => `${sr.name}: ${formatCents(sr.values[i])}`)],
  });
  return s("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": description },
    axis(range, y),
    labels.map((l, i) => s("text", { x: x(i), y: H - 8, "text-anchor": "middle" }, l)),
    series.map((sr, n) => seriesLine(sr, n, x, y, labelYs[n])),
    hover);
}
