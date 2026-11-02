// The About part of the Settings menu: the version and links to the guide, privacy statement and licences.
// The addresses come from the Home Base (GET /api/local/about), so no web address is written in the dashboard.

import { getAbout } from "./api/endpoints.js";
import { fill, h } from "./dom.js";

// In the Windows app's window a link must open in the default browser, not inside the app window. The app
// offers open_link(url) for that (desktop/budget_buddy_desktop/links.py, which checks the address too).
// Returns true when it took the click; in a normal browser the link opens in a new tab as usual.
export function openInSystemBrowser(event, url, win = globalThis.window) {
  const open = win?.pywebview?.api?.open_link;
  if (typeof open !== "function") return false;
  event.preventDefault();
  Promise.resolve(open(url)).catch(() => {});
  return true;
}

export function aboutLink({ label, url }) {
  const link = h("a", { href: url, target: "_blank", rel: "noopener noreferrer",
    "aria-label": `${label} (opens in your web browser)` }, label);
  link.addEventListener("click", (event) => openInSystemBrowser(event, url));
  return h("li", {}, link);
}

export function aboutContent(about) {
  return [
    h("p", {}, `Budget Buddy version ${about.version}`),
    h("p", { class: "muted" }, "These open in your web browser and need the internet. Budget Buddy itself " +
      "never needs it."),
    h("ul", { class: "about-links" }, about.links.map(aboutLink)),
  ];
}

// A "About" section that loads when first opened.
export function aboutSection() {
  const body = h("div", { class: "about-body", "aria-live": "polite" }, h("p", { class: "muted" }, "Loading..."));
  const section = h("details", { class: "about" }, h("summary", {}, "About"), body);
  let loaded = false;
  section.addEventListener("toggle", async () => {
    if (!section.open || loaded) return;
    try {
      fill(body, aboutContent(await getAbout()));
      loaded = true;
    } catch (err) {
      fill(body, h("p", { class: "error", role: "alert" }, err.message));
    }
  });
  return section;
}
