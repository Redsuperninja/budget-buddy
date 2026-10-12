// Shown instead of the dashboard on another computer that hasn't joined yet (ADR-0009): type the code
// from the Budget Buddy computer and a name for this one. Joining sets a cookie, then the page reloads.

import { joinThisComputer } from "../../api/endpoints.js";
import { fill } from "../../dom.js";
import { form } from "../../form.js";
import { card, empty } from "../../widgets.js";

export function render(root) {
  fill(root, card("Connect to Budget Buddy",
    empty("On the Budget Buddy computer, open Devices, then Other devices, and click Allow another device. " +
      "Type the code it shows."),
    form([
      { name: "code", label: "Code", required: true, maxlength: 20, placeholder: "ABCD-EFGH" },
      { name: "name", label: "A name for this computer or phone", required: true, maxlength: 100, placeholder: "Kitchen laptop" },
    ], "Connect", async (v) => {
      await joinThisComputer({ code: v.code, name: v.name });
      location.reload();
    })));
}
