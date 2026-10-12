// The list of connected phones, with a Remove button for each.

import { listDevices, revokeDevice } from "../../api/endpoints.js";
import { fill, h, showError } from "../../dom.js";
import { empty, table } from "../../widgets.js";

// Returns the box to put on the page and showDevices(), which redraws it and returns all devices.
export function phoneList() {
  const box = h("div", {});

  async function showDevices() {
    const devices = await listDevices();
    const active = devices.filter((d) => !d.revoked);
    fill(box, active.length
      ? table(["Phone", "Paired", "Last sync", ""], active.map((d) => [
          `${d.name}${d.platform ? ` (${d.platform})` : ""}`,
          d.paired_at.slice(0, 10),
          d.last_sync_at ? d.last_sync_at.slice(0, 16).replace("T", " ") : "not yet",
          h("button", { class: "danger", type: "button", onclick: () => removeDevice(d) }, "Remove")]))
      : empty("No phones are connected yet."));
    return devices;
  }

  async function removeDevice(d) {
    if (!confirm(`Remove "${d.name}"? It will stop syncing right away. You can pair it again later.`)) return;
    try {
      await revokeDevice(d.id);
      await showDevices();
    } catch (err) {
      showError(box, err);
    }
  }

  return { box, showDevices };
}
