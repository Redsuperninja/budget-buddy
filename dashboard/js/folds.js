// Which cards you folded up, remembered in this browser only. A card is known by its title without numbers, so
// "Dividends in 2026" stays folded in 2027 too. Never throws, even when the browser blocks storage.

const KEY = "budget-buddy-folds";

export function foldId(title) {
  return String(title).toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-+|-+$/g, "");
}

// storage: window.localStorage, or null when the browser blocks it. Returns { id: open } for the cards you changed.
export function loadFolds(storage) {
  try {
    const saved = JSON.parse(storage ? storage.getItem(KEY) : null);
    if (!saved || typeof saved !== "object" || Array.isArray(saved)) return {};
    return Object.fromEntries(Object.entries(saved).filter(([, open]) => typeof open === "boolean"));
  } catch {
    return {};
  }
}

// Open or folded on first sight: what you chose last time, or the card's own default.
export const isOpen = (folds, id, openByDefault) => (id in folds ? folds[id] : openByDefault);

export function saveFold(storage, id, open) {
  try {
    if (storage) storage.setItem(KEY, JSON.stringify({ ...loadFolds(storage), [id]: open }));
  } catch {
    /* private mode or storage turned off: the card stays as you left it until the page closes */
  }
}
