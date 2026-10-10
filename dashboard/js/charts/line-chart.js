// A line chart over months (up to three series), with names at the line ends and a hover guide. With one series
// and `area`, the space under the line is lightly shaded. series: [{ name, values }] in cents, one value per label;
// labels: ["Jan 2026", "Feb", ...]. Drawn `width` wide (charts/fit.js): narrow charts label every other month.

import { formatCents, shortDollars } from "../money.js";
import { hoverGuide } from "./hover.js";
import { linear, niceRange, ticks } from "./scale.js";
import { s } from "./svg.js";

const H = 260;
const PAD = { left: 56, top: 12, bottom: 28 };
const LABEL_GAP = 14;
const MONTH_LABEL_PX = 46; // a month label needs about this much room

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

// Label every n-th point so labels don't run into each other: 1, 2, 3...
export function labelEvery(count, span, px = MONTH_LABEL_PX) {
  return count > 1 ? Math.max(1, Math.ceil((px * (count - 1)) / span)) : 1;
}

function axis(range, y, right) {
  return ticks(range).map((t) => s("g", {},
    s("line", { class: t === 0 ? "grid zero" : "grid", x1: PAD.left, x2: right, y1: y(t), y2: y(t) }),
    s("text", { x: PAD.left - 8, y: y(t) + 4, "text-anchor": "end" }, shortDollars(t))));
}

function seriesLine(sr, n, { x, y, labelY, area, base }) {
  const points = sr.values.map((v, i) => `${x(i)},${y(v)}`);
  const last = sr.values.length - 1;
  return s("g", { class: `series-${n + 1}` },
    area ? s("path", { class: "area", d: `M${x(0)},${base}L${points.join("L")}L${x(last)},${base}Z` }) : null,
    s("path", { class: "line", d: `M${points.join("L")}` }),
    sr.values.map((v, i) => (i === last ? s("circle", { class: "dot", cx: x(i), cy: y(v), r: 4 }) : null)),
    s("text", { class: "label", x: x(last) + 10, y: labelY + 4 }, sr.name));
}

export function lineChart(series, labels, description, width = 640, { area = false } = {}) {
  const right = width - Math.min(92, Math.max(...series.map((sr) => sr.name.length)) * 7 + 18);
  const all = series.flatMap((sr) => sr.values);
  const range = niceRange(Math.min(...all), Math.max(...all), 4);
  const y = linear(range, H - PAD.bottom, PAD.top);
  const span = right - PAD.left;
  const x = (i) => PAD.left + (labels.length > 1 ? (i * span) / (labels.length - 1) : 0);
  const every = labelEvery(labels.length, span);
  const labelYs = spreadLabels(series.map((sr) => y(sr.values[sr.values.length - 1])));
  const hover = hoverGuide({
    count: labels.length, x, top: PAD.top, bottom: H - PAD.bottom, width,
    texts: (i) => [labels[i], ...series.map((sr) => `${sr.name}: ${formatCents(sr.values[i])}`)],
  });
  const shade = area && series.length === 1;
  return s("svg", { class: "chart", viewBox: `0 0 ${width} ${H}`, width, role: "img", "aria-label": description },
    axis(range, y, right),
    labels.map((l, i) => ((labels.length - 1 - i) % every === 0
      ? s("text", { x: x(i), y: H - 8, "text-anchor": "middle" }, l) : null)),
    series.map((sr, n) => seriesLine(sr, n, { x, y, labelY: labelYs[n], area: shade, base: y(Math.max(0, range.lo)) })),
    hover);
}
