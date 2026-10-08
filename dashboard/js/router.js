// Navigation: one button per screen, the #hash picks the screen, and screens can redraw
// themselves with reload() or register clean-up (stopping timers) with onLeave().

import { fill, h, showError } from "./dom.js";

let screens = [];
let leaveHandlers = [];
let nav;
let view;

const currentId = () => location.hash.slice(1) || screens[0].id;

export const onLeave = (fn) => leaveHandlers.push(fn);

// Redraw the current screen, optionally with a choice to keep ({ month } or { year }).
export const reload = (options) => show(currentId(), options);

async function show(id, options = {}) {
  for (const fn of leaveHandlers) fn();
  leaveHandlers = [];
  const screen = screens.find((s) => s.id === id) || screens[0];
  for (const button of nav.children) {
    if (button.dataset.id === screen.id) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  const root = h("div", {}, h("p", { class: "muted" }, "Loading..."));
  fill(view, root);
  try {
    await screen.render(root, options);
  } catch (err) {
    showError(root, err);
  }
}

// table: [{ id, label, render(root, options) }, ...]
export function start(table) {
  screens = table;
  nav = document.getElementById("nav");
  view = document.getElementById("view");
  for (const { id, label } of screens) {
    nav.append(h("button", { type: "button", "data-id": id, onclick: () => { location.hash = id; } }, label));
  }
  window.addEventListener("hashchange", () => show(currentId()));
  show(currentId());
}
