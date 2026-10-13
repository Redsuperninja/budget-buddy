// Reusable page pieces built from dom.js: cards, tables, pickers and short notes.

import { browserStorage, h } from "./dom.js";
import { foldId, isOpen, loadFolds, saveFold } from "./folds.js";

export const empty = (text) => h("p", { class: "muted" }, text);
export const note = (text) => h("div", { class: "note" }, text);
// A longer explanation, folded under "About these numbers" so the numbers come first. Never for warnings.
export const aboutNote = (text) =>
  h("details", { class: "about" }, h("summary", {}, "About these numbers"), h("div", { class: "note" }, text));
// Marks a page piece as a power-user tool: shown only in the All tools view (Settings, View).
export function advanced(el) {
  el.classList.add("advanced");
  return el;
}

// A card with a title folds up when you click its title, and stays the way you left it (folds.js). A card without a
// title is a plain box. formCard starts folded: forms to add something, so the lists come first.
export function foldCard(title, { open = true } = {}, ...children) {
  const id = foldId(title);
  const storage = browserStorage();
  const el = h("details", { class: "card fold", open: isOpen(loadFolds(storage), id, open) },
    h("summary", {}, h("h2", {}, title)), children);
  // Also fires once as the page draws an open card: only a change from what's remembered is saved.
  el.addEventListener("toggle", () => {
    if (el.open !== isOpen(loadFolds(storage), id, open)) saveFold(storage, id, el.open);
  });
  return el;
}

export const card = (title, ...children) =>
  (title ? foldCard(title, {}, ...children) : h("section", { class: "card" }, children));
export const formCard = (title, ...children) => foldCard(title, { open: false }, ...children);

export function statCard(label, text, extra) {
  return h("div", { class: "card" }, h("div", { class: "muted" }, label), h("div", { class: "big" }, text), extra);
}

// options: [[value, label], ...]
export function select(options, { value, ...attrs } = {}) {
  const el = h("select", attrs, options.map(([v, text]) => h("option", { value: v }, text)));
  if (value !== undefined && value !== null) el.value = String(value);
  return el;
}

// rows: lists of cells (text or nodes). rightAligned: column numbers to right-align (numbers).
// advancedColumns: column numbers shown only in the All tools view. Each cell carries its column name, so on a
// phone app.css can show a row of a wider table (three or more columns) as a small card of "name: value" lines.
export function table(headers, rows, rightAligned = [], advancedColumns = []) {
  const cls = (i) => [rightAligned.includes(i) ? "num" : "", advancedColumns.includes(i) ? "advanced" : ""]
    .join(" ").trim() || null;
  return h("div", { class: "scroll" }, h("table", { class: headers.length > 2 ? "stack" : null },
    h("thead", {}, h("tr", {}, headers.map((t, i) => h("th", { class: cls(i) }, t)))),
    h("tbody", {}, rows.map((row) =>
      h("tr", {}, row.map((cell, i) => h("td", { class: cls(i), "data-label": headers[i] || null }, cell)))))));
}
