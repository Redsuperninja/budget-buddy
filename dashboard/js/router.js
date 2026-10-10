// Navigation: a few section buttons on top, and a row of page tabs under them when a section has more
// than one page. The #hash names the page, so old links like #donations still work, and can carry choices for
// it (#transactions?sorted=none). Pages marked advanced get a tab only in the All tools view. Screens can redraw
// themselves with reload() or register clean-up (stopping timers) with onLeave().

import { fill, h, showError } from "./dom.js";

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

function showTabs(section, page) {
  if (section.pages.length < 2) {
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

async function show(id, options = {}) {
  for (const fn of leaveHandlers) fn();
  leaveHandlers = [];
  const page = pages.find((p) => p.id === id) || sections.find((s) => s.id === id)?.pages[0] || pages[0];
  const section = sections.find((s) => s.pages.includes(page));
  markCurrent(nav, section.id);
  showTabs(section, page);
  const root = h("div", {}, h("p", { class: "muted" }, "Loading..."));
  fill(view, root);
  try {
    await page.render(root, options);
  } catch (err) {
    showError(root, err);
  }
}

// table: [{ id, label, pages: [{ id, label, render(root, options), advanced? }, ...] }, ...]
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
  show(currentId(), hashOptions());
}
