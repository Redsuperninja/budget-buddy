// The category dropdown in a transaction's row (Transactions and Auto-sort pages). Shows what kind of transfer a
// linked one is, "auto-sorted" when a rule picked the category, and when a pick teaches a new auto-sort rule.

import { updateTransaction } from "../api/endpoints.js";
import { h } from "../dom.js";
import { idOrNull, pickOptions } from "../fields.js";
import { transferTypeLabel } from "../labels.js";
import { select } from "../widgets.js";

export function categoryPicker(t, categories) {
  const picker = select(pickOptions(categories, "(no category)"),
    { value: t.category_id || "", "aria-label": "Category" });
  const tagText = t.transfer_type ? ` Transfer: ${transferTypeLabel(t.transfer_type)}`
    : t.category_source === "rule" ? " auto-sorted" : "";
  const tag = h("span", { class: "muted" }, tagText);
  const note = h("span", { class: "muted", role: "status" });
  picker.addEventListener("change", async () => {
    try {
      const saved = await updateTransaction(t.id, { category_id: idOrNull(picker.value) });
      tag.textContent = "";
      note.textContent = saved.learned_rule
        ? ` Saved. From now on, "${saved.learned_rule}" is sorted here automatically (see Auto-sort).`
        : " Saved";
    } catch (err) {
      note.textContent = ` ${err.message}`;
    }
  });
  return h("span", {}, picker, tag, note);
}
