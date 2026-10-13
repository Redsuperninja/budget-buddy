// The "Settings" menu in the page header: Colors (Match my computer, Light, Dark) and View (Simple or All
// tools). Applies the saved choices as soon as the page starts.

import { browserStorage, h } from "./dom.js";
import { THEMES, applyTheme, loadTheme, saveTheme } from "./theme.js";
import { VIEWS, applyView, loadView, saveView } from "./view.js";
import { select } from "./widgets.js";

// A labelled picker that applies and remembers its choice.
function picker(label, name, choices, { load, save, apply }) {
  const storage = browserStorage();
  const root = document.documentElement;
  const choice = load(storage);
  apply(root, choice);
  const el = select(choices, {
    value: choice, name,
    onchange: () => { save(storage, el.value); apply(root, el.value); },
  });
  return h("label", {}, label, el);
}

export function addSettingsMenu() {
  const colors = picker("Colors", "theme", THEMES, { load: loadTheme, save: saveTheme, apply: applyTheme });
  const view = picker("View", "view", VIEWS, { load: loadView, save: saveView, apply: applyView });
  const menu = h("details", { class: "settings" },
    h("summary", {}, "Settings"),
    h("div", { class: "settings-panel" }, view,
      h("p", { class: "muted" }, "Simple shows what most people need. All tools adds import history, auto-sort " +
        "rules, broker files, live prices and more."),
      colors));
  // Clicking anywhere else closes the menu.
  document.addEventListener("click", (event) => { if (!menu.contains(event.target)) menu.open = false; });
  document.querySelector("header").append(menu);
}
