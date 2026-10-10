// Charts drawn at the width of their card, so their text is its real size on a phone too: draw(width) returns an
// SVG, and it's drawn again when the card's width changes (window resized, phone turned).

import { fill, h } from "../dom.js";

export const MIN_WIDTH = 280;
export const MAX_WIDTH = 960;
const DEFAULT_WIDTH = 640; // before the card is on the page, or without ResizeObserver
const STEP = 8; // smaller changes aren't worth a redraw

export const clampWidth = (px) => Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, px || DEFAULT_WIDTH)));

export function fitted(draw) {
  const holder = h("div", { class: "chart-fit" });
  let drawn = DEFAULT_WIDTH;
  holder.append(draw(drawn));
  if (typeof ResizeObserver === "function") {
    new ResizeObserver(() => {
      const width = clampWidth(holder.clientWidth);
      if (Math.abs(width - drawn) < STEP) return;
      drawn = width;
      fill(holder, draw(width));
    }).observe(holder);
  }
  return holder;
}

// About how many characters of 12px text fit in `px` (for cutting long labels short).
export const charsIn = (px) => Math.max(4, Math.floor(px / 7));

export function clip(text, px) {
  const room = charsIn(px);
  return text.length > room ? `${text.slice(0, room - 1)}…` : text;
}
