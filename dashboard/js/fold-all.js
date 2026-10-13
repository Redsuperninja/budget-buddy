// "Fold all" and "Open all" above a page with three or more folding cards, so a long page can be skimmed by its
// titles. Each card remembers the change, as if its title had been clicked (widgets.js foldCard).

import { h } from "./dom.js";

const cards = (root) => [...root.querySelectorAll("details.fold.card")];

// root: the page as drawn. Returns the bar, or null for a short page. Cards are looked up on each click, since
// pages redraw parts of themselves.
export function foldAllBar(root) {
  if (cards(root).length < 3) return null;
  const setAll = (open) => { for (const el of cards(root)) el.open = open; };
  return h("div", { class: "fold-all no-print" },
    h("button", { class: "link", type: "button", onclick: () => setAll(false) }, "Fold all"),
    h("button", { class: "link", type: "button", onclick: () => setAll(true) }, "Open all"));
}
