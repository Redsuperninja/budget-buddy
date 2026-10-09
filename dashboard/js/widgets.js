// Reusable page pieces built from dom.js: cards, tables, pickers and short notes.

import { h } from "./dom.js";

export const empty = (text) => h("p", { class: "muted" }, text);
export const note = (text) => h("div", { class: "note" }, text);
// Marks a page piece as a power-user tool: shown only in the All tools view (Settings, View).
export function advanced(el) {
  el.classList.add("advanced");
  return el;
}

export const card = (title, ...children) =>
  h("section", { class: "card" }, title ? h("h2", {}, title) : null, children);

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
