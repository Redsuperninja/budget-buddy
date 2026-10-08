// Connect phone: show the pairing QR with a countdown and notice when a phone pairs.

import { startPairing as requestPairing, listDevices } from "../api/endpoints.js";
import { fill, h, showError } from "../dom.js";
import { onLeave } from "../router.js";
import { card, empty } from "../widgets.js";
import { phoneList } from "./phone-list.js";

const POLL_MS = 3000; // also lets the Home Base close the home-network listener after the code runs out

export async function render(root) {
  const area = h("div", {});
  const { box: deviceBox, showDevices } = phoneList();
  let timers = [];
  let qrUrl = null;
  const stopTimers = () => { timers.forEach(clearInterval); timers = []; };
  onLeave(() => { stopTimers(); if (qrUrl) URL.revokeObjectURL(qrUrl); });

  async function startPairing() {
    stopTimers();
    const knownIds = new Set((await listDevices()).map((d) => d.id));
    const p = await requestPairing();
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
