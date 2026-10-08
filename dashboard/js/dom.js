// Building the page. Everything is made with createElement and textContent, so nothing that comes
// from the API can run as code. Bigger pieces are in widgets.js (cards, tables) and form.js (forms).

export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2), value);
    } else if (key === "value" || key === "checked" || key === "disabled") {
      el[key] = value;
    } else {
      el.setAttribute(key, value === true ? "" : String(value));
    }
  }
  append(el, children);
  return el;
}

// Adds children (strings, nodes, nested lists); null, undefined and false are skipped.
function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

// Replace what is inside el. Empty parts (null, false) are skipped, so the word "null" never shows.
export function fill(el, ...children) {
  el.textContent = "";
  append(el, children);
}

export const showError = (el, err) => fill(el, h("p", { class: "error", role: "alert" }, err.message));
