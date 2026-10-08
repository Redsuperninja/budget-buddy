// Reusable page pieces built from dom.js: cards, tables, pickers and short notes.

import { h } from "./dom.js";

export const empty = (text) => h("p", { class: "muted" }, text);
export const note = (text) => h("div", { class: "note" }, text);
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
export function table(headers, rows, rightAligned = []) {
  const cls = (i) => (rightAligned.includes(i) ? "num" : null);
  return h("div", { class: "scroll" }, h("table", {},
    h("thead", {}, h("tr", {}, headers.map((t, i) => h("th", { class: cls(i) }, t)))),
    h("tbody", {}, rows.map((row) => h("tr", {}, row.map((cell, i) => h("td", { class: cls(i) }, cell)))))));
}
