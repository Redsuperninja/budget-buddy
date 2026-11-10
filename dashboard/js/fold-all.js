// "Fold all" and "Open all" above a page with three or more folding cards, so a long page can be skimmed by its
// titles. Each card remembers the change, as if its title had been clicked (widgets.js foldCard). Only the page's
// own cards count: a card inside another card, or one hidden in the simple view, is left alone. A button that
// would change nothing is switched off, so it is always clear which way the page can still go.

import { h } from "./dom.js";

// states: one true (open) or false (folded) per card. What each button can still do.
export const foldAvailability = (states) => ({
  canFold: states.some(Boolean),
  canOpen: states.some((open) => !open),
});

const shown = (el) => !el.closest(".advanced") || el.getClientRects().length > 0;
const cards = (root) => [...root.querySelectorAll("details.fold.card")]
  .filter((el) => !el.parentElement.closest("details.fold") && shown(el));

// root: the page as drawn. Returns the bar, or null for a short page. Cards are looked up on each click, since
// pages redraw parts of themselves.
export function foldAllBar(root) {
  if (cards(root).length < 3) return null;
  const foldButton = h("button", { class: "fold-up", type: "button" }, "Fold all");
  const openButton = h("button", { class: "fold-down", type: "button" }, "Open all");
  const update = () => {
    const { canFold, canOpen } = foldAvailability(cards(root).map((el) => el.open));
    foldButton.disabled = !canFold;
    openButton.disabled = !canOpen;
  };
  const setAll = (open) => {
    for (const el of cards(root)) el.open = open;
    update();
  };
  foldButton.onclick = () => setAll(false);
  openButton.onclick = () => setAll(true);
  root.addEventListener("toggle", update, true); // a card opened or folded by hand (toggle doesn't bubble)
  update();
  return h("div", { class: "fold-all no-print" },
    h("div", { class: "seg", role: "group", "aria-label": "Fold or open every card" }, foldButton, openButton));
}
