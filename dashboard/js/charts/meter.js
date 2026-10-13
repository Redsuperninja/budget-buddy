// One number against a limit: a thin bar (meter) or a ring. The filled part is the theme green, red once past the
// limit; the unfilled part is a lighter step of the same green. SVG, since the page's security rules don't allow
// inline styles. used: 0 to 1 (more shows as full); alarm: show it red (by default, once past the limit).

import { s } from "./svg.js";

export function meter(used, label, alarm = used > 1) {
  const share = Math.max(0, used);
  return s("svg", { class: `meter${alarm ? " over" : ""}`, viewBox: "0 0 100 6", preserveAspectRatio: "none",
    role: "img", "aria-label": label },
  s("rect", { class: "meter-track", x: 0, y: 0, width: 100, height: 6, rx: 3 }),
  share > 0 ? s("rect", { class: "meter-fill", x: 0, y: 0, width: Math.min(1, share) * 100, height: 6, rx: 3 }) : null);
}

const R = 26;
const AROUND = 2 * Math.PI * R;

// A ring that fills clockwise from the top, with `middle` (a short text, like "57%") in its center.
export function ring(used, label, middle, alarm = used > 1) {
  const share = Math.max(0, used);
  return s("svg", { class: `ring${alarm ? " over" : ""}`, viewBox: "0 0 64 64", role: "img", "aria-label": label },
    s("circle", { class: "ring-track", cx: 32, cy: 32, r: R }),
    share > 0 ? s("circle", { class: "ring-fill", cx: 32, cy: 32, r: R, transform: "rotate(-90 32 32)",
      "stroke-dasharray": `${(Math.min(1, share) * AROUND).toFixed(2)} ${AROUND.toFixed(2)}` }) : null,
    s("text", { x: 32, y: 36.5, "text-anchor": "middle" }, middle));
}
