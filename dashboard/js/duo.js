// Two cards side by side (Home's charts). They stay the same size, so when one is folded or opened by hand
// its neighbour follows, and the pair never shows a short card beside a tall one with an empty gap. When the
// window is narrow enough to stack them, each folds on its own.

import { h } from "./dom.js";

export function duo(...cards) {
  const row = h("div", { class: "duo" }, cards);
  const sideBySide = () => new Set(cards.map((card) => card.offsetTop)).size === 1;
  // "toggle" doesn't bubble, so listen while it travels down (capture).
  row.addEventListener("toggle", (event) => {
    if (!cards.includes(event.target) || !sideBySide()) return;
    for (const other of cards) other.open = event.target.open; // an unchanged value fires nothing more
  }, true);
  return row;
}
