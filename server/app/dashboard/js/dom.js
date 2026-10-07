// Building the page. Everything is made with createElement and textContent, so nothing that comes
// from the API can run as code. The form builder gives every form the same submit and error handling.

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

// Run an action and say how it went in a small note next to the control.
export async function saveWithNote(noteEl, action) {
  try {
    await action();
    noteEl.textContent = " Saved";
  } catch (err) {
    noteEl.textContent = ` ${err.message}`;
  }
}

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

// A form from field descriptions: { name, label, type, value, options, required, ... }.
// onSubmit gets the typed-in text by field name. If it throws, the message shows under the form.
export function form(fields, submitLabel, onSubmit) {
  const message = h("p", { class: "error", role: "alert", hidden: true });
  const inputs = {};
  const labels = fields.map((f) => {
    inputs[f.name] = f.options
      ? select(f.options, { name: f.name, value: f.value })
      : h("input", {
          name: f.name, type: f.type || "text", value: f.value ?? "", placeholder: f.placeholder,
          required: f.required, maxlength: f.maxlength, inputmode: f.inputmode, autocomplete: "off",
        });
    return h("label", {}, f.label, inputs[f.name]);
  });
  const button = h("button", { class: "primary", type: "submit" }, submitLabel);
  return h("form", {
    novalidate: true,
    onsubmit: async (event) => {
      event.preventDefault();
      message.hidden = true;
      const values = Object.fromEntries(Object.entries(inputs).map(([name, input]) => [name, input.value]));
      button.disabled = true;
      try {
        await onSubmit(values);
      } catch (err) {
        message.textContent = err.message;
        message.hidden = false;
      } finally {
        button.disabled = false;
      }
    },
  }, labels, h("div", { class: "wide" }, button), h("div", { class: "wide" }, message));
}
