// Connect phone: show the pairing QR with a countdown, notice when a phone pairs, list and remove phones.

import { api } from "../api.js";
import { card, empty, fill, h, showError, table } from "../dom.js";
import { onLeave } from "../router.js";

const POLL_MS = 3000; // also lets the Home Base close the home-network listener after the code runs out

export async function render(root) {
  const area = h("div", {});
  const deviceBox = h("div", {});
  let timers = [];
  let qrUrl = null;
  const stopTimers = () => { timers.forEach(clearInterval); timers = []; };
  onLeave(() => { stopTimers(); if (qrUrl) URL.revokeObjectURL(qrUrl); });

  async function showDevices() {
    const devices = await api("GET", "/api/local/devices");
    const active = devices.filter((d) => !d.revoked);
    fill(deviceBox, active.length
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
      await api("POST", `/api/local/devices/${d.id}/revoke`);
      await showDevices();
    } catch (err) {
      showError(deviceBox, err);
    }
  }

  async function startPairing() {
    stopTimers();
    const knownIds = new Set((await api("GET", "/api/local/devices")).map((d) => d.id));
    const p = await api("POST", "/api/local/pairing");
    if (qrUrl) URL.revokeObjectURL(qrUrl);
    qrUrl = URL.createObjectURL(new Blob([p.qr_svg], { type: "image/svg+xml" }));
    const countdown = h("p", { class: "muted" });
    fill(area,
      h("p", {}, "On your phone: open Budget Buddy, go to Settings, then Connect, and scan this picture."),
      h("img", { class: "qr", src: qrUrl, alt: "Pairing QR code for your phone" }),
      countdown,
      p.phone_can_connect ? null
        : h("div", { class: "note" }, p.message || "Your phone may not be able to reach this computer yet."),
      h("details", {}, h("summary", {}, "Show code as text"),
        empty("If the camera can't scan, paste this into the phone app. Don't share it: it works once, for a short time."),
        h("textarea", { class: "code", readonly: true, "aria-label": "Pairing code as text" }, p.payload_text)));

    const tick = () => {
      const left = p.expires_at - Math.floor(Date.now() / 1000);
      if (left > 0) {
        countdown.textContent = `Works for ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")} more.`;
        return;
      }
      stopTimers();
      fill(area, h("p", { class: "note" }, "That code has expired. Click \"Show pairing code\" for a new one."));
      showDevices().catch(() => {});
    };
    tick();
    timers.push(setInterval(tick, 1000));
    timers.push(setInterval(async () => {
      try {
        const devices = await showDevices();
        if (devices.some((d) => !knownIds.has(d.id) && !d.revoked)) {
          stopTimers();
          fill(area, h("p", { class: "ok", role: "status" }, "New phone paired"));
        }
      } catch { /* try again in a few seconds */ }
    }, POLL_MS));
  }

  fill(root,
    card("Connect a phone",
      h("p", {}, "Your phone and this computer need to be on the same home Wi-Fi."),
      h("button", { class: "primary", type: "button", onclick: async () => {
        try { await startPairing(); } catch (err) { showError(area, err); }
      } }, "Show pairing code"),
      area),
    card("Connected phones", deviceBox));
  await showDevices();
}
