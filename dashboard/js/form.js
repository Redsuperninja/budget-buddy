// Forms: one engine for every form's submit button, error message and typed-in values.

import { h } from "./dom.js";
import { select } from "./widgets.js";

// Run an action and say how it went in a small note next to the control.
export async function saveWithNote(noteEl, action) {
  try {
    await action();
    noteEl.textContent = " Saved";
  } catch (err) {
    noteEl.textContent = ` ${err.message}`;
  }
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
          required: f.required, maxlength: f.maxlength, inputmode: f.inputmode, autocomplete: f.autocomplete || "off",
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
