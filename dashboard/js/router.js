// Navigation: a few section buttons on top, and a row of page tabs under them when a section has more
// than one page. The #hash names the page, so old links like #donations still work, and can carry choices for
// it (#transactions?sorted=none). Pages marked advanced get a tab only in the All tools view. Screens can redraw
// themselves with reload() or register clean-up (stopping timers) with onLeave().

import { fill, h, showError } from "./dom.js";
import { foldAllBar } from "./fold-all.js";

let sections = [];
let pages = [];
let leaveHandlers = [];
let nav;
let subnav;
let view;

const hashParts = () => location.hash.slice(1).split("?");
const currentId = () => hashParts()[0] || pages[0].id;
const hashOptions = () => Object.fromEntries(new URLSearchParams(hashParts()[1] || ""));
const go = (id) => { location.hash = id; };

export const onLeave = (fn) => leaveHandlers.push(fn);

// Redraw the current screen, optionally with a choice to keep ({ month } or { year }).
export const reload = (options) => show(currentId(), options);

function markCurrent(container, id) {
  for (const button of container.children) {
    if (button.dataset.id === id) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
}

// The tabs a person can see: advanced pages only in the All tools view (or while they are the open page).
export const visiblePages = (section, page, allTools) =>
  section.pages.filter((p) => !p.advanced || allTools || p.id === page.id);

let shownTabs = null; // { section, page } of the tabs on screen, so a change of view can redraw them

function showTabs(section, page) {
  shownTabs = { section, page };
  const allTools = document.documentElement.dataset.view === "all";
  if (visiblePages(section, page, allTools).length < 2) { // Home alone is not worth a row of one tab
    fill(subnav);
    subnav.hidden = true;
    return;
  }
  fill(subnav, section.pages.map(({ id, label, advanced }) =>
    h("button", { type: "button", "data-id": id, class: advanced ? "advanced" : null, onclick: () => go(id) }, label)));
  subnav.setAttribute("aria-label", `${section.label} pages`);
  subnav.hidden = false;
  markCurrent(subnav, page.id);
}

let shownBefore = false;

// Move the keyboard/screen-reader position to the page's first heading, without scrolling.
function focusHeading(root) {
  const heading = root.querySelector("h2, h3");
  if (!heading) return;
  heading.setAttribute("tabindex", "-1");
  heading.focus({ preventScroll: true });
}

async function show(id, options = {}) {
  for (const fn of leaveHandlers) fn();
  leaveHandlers = [];
  const page = pages.find((p) => p.id === id) || sections.find((s) => s.id === id)?.pages[0] || pages[0];
  const section = sections.find((s) => s.pages.includes(page));
  markCurrent(nav, section.id);
  showTabs(section, page);
  const root = h("div", {}, h("p", { class: "muted", role: "status" }, "Loading..."));
  fill(view, root);
  try {
    const screen = page.render ? page : await page.load(); // load() imports the page's module on first use
    await screen.render(root, options);
    const bar = foldAllBar(root);
    if (bar && root.isConnected) view.prepend(bar);
    if (shownBefore) focusHeading(root); // so a screen reader starts at the new page's title
    shownBefore = true;
  } catch (err) {
    showError(root, err, () => show(id, options));
    shownBefore = true;
  }
}

// table: [{ id, label, pages: [{ id, label, load() -> module with render(root, options), advanced? }, ...] }, ...]
// A section button opens its first page.
export function start(table) {
  sections = table;
  pages = sections.flatMap((s) => s.pages);
  nav = document.getElementById("nav");
  subnav = document.getElementById("subnav");
  view = document.getElementById("view");
  for (const { id, label, pages: [first] } of sections) {
    nav.append(h("button", { type: "button", "data-id": id, onclick: () => go(first.id) }, label));
  }
  window.addEventListener("hashchange", () => show(currentId(), hashOptions()));
  // Switching between Simple and All tools adds or removes tabs (and Home's lone tab) without a page change.
  new MutationObserver(() => shownTabs && showTabs(shownTabs.section, shownTabs.page))
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-view"] });
  show(currentId(), hashOptions());
}
