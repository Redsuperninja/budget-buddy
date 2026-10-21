// Part of the Tax summary: choose a filing status so the page shows only its standard deduction, or
// "Not set: show all". It only picks which numbers are shown; it never changes any of them.

import { saveTaxPreferences } from "../../api/endpoints.js";
import { h } from "../../dom.js";
import { FILING_STATUSES } from "../../labels.js";
import { reload } from "../../router.js";
import { select } from "../../widgets.js";

const NOT_SET = "Not set: show all";

export function filingStatusControl(current, year) {
  const picker = select([["", NOT_SET], ...FILING_STATUSES], { value: current || "", id: "filing-status" });
  const note = h("span", { class: "muted", role: "status" });
  picker.addEventListener("change", async () => {
    try {
      await saveTaxPreferences({ filing_status: picker.value || null });
      await reload({ year });
    } catch (err) {
      note.textContent = ` ${err.message}`;
    }
  });
  return h("p", { class: "inline-form no-print" },
    h("label", { for: "filing-status" }, "Your filing status "), picker, note);
}
