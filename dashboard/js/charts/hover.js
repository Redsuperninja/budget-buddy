// The hover guide for line charts: a vertical line at the month under the pointer, and a box listing
// every series' value for that month. Drawn inside the SVG, so it needs no page styles.

import { s } from "./svg.js";

const LINE_HEIGHT = 16;

function setAll(el, attrs) {
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
}

// texts(i): the lines to show for point i. x(i): its position. Returns the elements to add to the chart.
export function hoverGuide({ count, x, top, bottom, width, texts }) {
  const lineCount = texts(0).length;
  const guide = s("line", { class: "crosshair", y1: top, y2: bottom });
  const box = s("rect", { class: "tip-box", rx: 6, height: 8 + lineCount * LINE_HEIGHT });
  const lines = Array.from({ length: lineCount }, () => s("text", {}));
  const tip = s("g", { class: "tip" }, box, lines);
  const layer = s("g", { visibility: "hidden" }, guide, tip);
  const hit = s("rect", { class: "hit", x: x(0), y: top, width: x(count - 1) - x(0) || 1, height: bottom - top });

  function nearestPoint(event) {
    const box = hit.ownerSVGElement.getBoundingClientRect();
    const px = ((event.clientX - box.left) * width) / box.width;
    const step = count > 1 ? x(1) - x(0) : 1;
    return Math.max(0, Math.min(count - 1, Math.round((px - x(0)) / step)));
  }

  function show(event) {
    const i = nearestPoint(event);
    const words = texts(i);
    const boxWidth = 16 + 7 * Math.max(...words.map((t) => t.length));
    const left = x(i) > width / 2 ? x(i) - boxWidth - 10 : x(i) + 10;
    setAll(guide, { x1: x(i), x2: x(i) });
    setAll(box, { x: left, y: top, width: boxWidth });
    words.forEach((word, n) => {
      lines[n].textContent = word;
      setAll(lines[n], { x: left + 8, y: top + 16 + n * LINE_HEIGHT });
    });
    layer.setAttribute("visibility", "visible");
  }

  hit.addEventListener("pointermove", show);
  hit.addEventListener("pointerleave", () => layer.setAttribute("visibility", "hidden"));
  return [layer, hit];
}
