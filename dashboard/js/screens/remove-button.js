// A small "Delete" button that asks first, runs the removal, then redraws. A refusal from the Home Base (like a
// purchase a sale still needs) is shown next to the button.

import { h } from "../dom.js";

// question: shown in the browser's "Are you sure?" box. action: the removal. onDone: called after it worked.
export function removeButton(question, action, onDone, label = "Delete") {
  const message = h("span", { class: "error", role: "alert" });
  const button = h("button", { class: "plain", type: "button", onclick: async () => {
    if (!window.confirm(question)) return;
    button.disabled = true;
    try {
      await action();
      await onDone();
    } catch (err) {
      message.textContent = ` ${err.message}`;
      button.disabled = false;
    }
  } }, label);
  return h("span", {}, button, message);
}
