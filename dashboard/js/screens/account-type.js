// Part of the Accounts screen: change an account's type, and for a retirement account what kind it is (Roth IRA,
// 401(k)...). A Roth IRA's contributions then count toward the IRA limit on the Investments page.

import { updateAccount } from "../api/endpoints.js";
import { h } from "../dom.js";
import { ACCOUNT_KINDS, RETIREMENT_TYPES } from "../labels.js";
import { reload } from "../router.js";
import { select } from "../widgets.js";

export function accountTypeCell(a) {
  const kind = select(ACCOUNT_KINDS, { value: a.kind, "aria-label": `Type of ${a.name}` });
  const subtype = select([["", "(pick one)"], ...RETIREMENT_TYPES],
    { value: a.retirement_type || "", "aria-label": `Kind of retirement account for ${a.name}` });
  const note = h("span", { class: "muted", role: "status" });
  const showSubtype = () => { subtype.hidden = kind.value !== "retirement"; };
  showSubtype();
  const save = async () => {
    showSubtype();
    try {
      const retirement = kind.value === "retirement";
      await updateAccount(a.id, { kind: kind.value, ...(retirement ? { retirement_type: subtype.value || null } : {}) });
      await reload();
    } catch (err) {
      note.textContent = ` ${err.message}`;
    }
  };
  kind.addEventListener("change", save);
  subtype.addEventListener("change", save);
  return h("span", { class: "inline-form" }, kind, subtype, note);
}
