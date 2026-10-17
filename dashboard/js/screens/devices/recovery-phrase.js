// The Backups page's "Your recovery phrase" (roadmap 24c): shown only after a warning, hidden again with
// a button or on leaving the page. Never stored in the browser.

import { showRecoveryPhrase } from "../../api/endpoints.js";
import { fill, h, showError } from "../../dom.js";
import { onLeave } from "../../router.js";
import { card, note } from "../../widgets.js";

export function phraseCard() {
  const area = h("div", {});
  const hide = () => fill(area, showButton);
  const showButton = h("button", { class: "primary", type: "button", onclick: async () => {
    if (!confirm("Make sure nobody else can see your screen. Show your recovery phrase now?")) return;
    showButton.disabled = true;
    try {
      const { phrase } = await showRecoveryPhrase();
      fill(area,
        h("p", { class: "big", translate: "no" }, phrase),
        note("Write it on paper, or keep it in a password manager. Don't save a photo or a file on this computer."),
        h("button", { type: "button", onclick: hide }, "Hide it"));
    } catch (err) {
      showError(area, err);
    } finally {
      showButton.disabled = false;
    }
  } }, "Show my recovery phrase");
  onLeave(hide);
  hide();
  return card("Your recovery phrase",
    h("p", {}, "These words unlock your data and your backups if this computer is lost or replaced. Save them " +
      "somewhere safe, away from this computer. Anyone with the words and a backup can read your data."),
    area);
}
