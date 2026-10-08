// Light, dark, or follow the computer's setting (the default). The choice is kept in this browser
// (or app window) only; app.css picks the colors with light-dark() and the data-theme attribute.

export const THEMES = [["system", "Match my computer"], ["light", "Light"], ["dark", "Dark"]];
const KEY = "budget-buddy-theme";

// Anything that isn't a known choice means "system".
export const parseTheme = (text) => (THEMES.some(([value]) => value === text) ? text : "system");

// storage: window.localStorage, or null when the browser blocks it. Never throws.
export function loadTheme(storage) {
  try {
    return parseTheme(storage ? storage.getItem(KEY) : null);
  } catch {
    return "system";
  }
}

export function saveTheme(storage, choice) {
  try {
    if (storage) storage.setItem(KEY, parseTheme(choice));
  } catch {
    /* private mode or storage turned off: the choice lasts until the page closes */
  }
}

// "system" removes data-theme, so the computer's setting decides.
export function applyTheme(root, choice) {
  const theme = parseTheme(choice);
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}
