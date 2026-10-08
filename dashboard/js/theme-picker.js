// The "Colors" picker in the page header: Match my computer, Light or Dark. Applies the saved choice
// as soon as the page starts.

import { h } from "./dom.js";
import { THEMES, applyTheme, loadTheme, saveTheme } from "./theme.js";
import { select } from "./widgets.js";

function browserStorage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function addThemePicker() {
  const storage = browserStorage();
  const root = document.documentElement;
  const choice = loadTheme(storage);
  applyTheme(root, choice);
  const picker = select(THEMES, {
    value: choice, name: "theme",
    onchange: () => { saveTheme(storage, picker.value); applyTheme(root, picker.value); },
  });
  document.querySelector("header").append(h("label", { class: "theme" }, "Colors", picker));
}
