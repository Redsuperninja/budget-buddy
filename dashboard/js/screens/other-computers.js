// Other computers: show a one-time join code for another computer on the home network, and list the
// computers that joined, with a Remove button for each (ADR-0009). Only on the Budget Buddy computer.

import { listComputers, newJoinCode, removeComputer } from "../api/endpoints.js";
import { fill, h, showError } from "../dom.js";
import { onLeave } from "../router.js";
import { card, empty, note, table } from "../widgets.js";

const POLL_MS = 3000; // notice a computer joining; lets the Home Base close the network after the code runs out

function computerList() {
  const box = h("div", {});
  async function show() {
    const computers = await listComputers();
    fill(box, computers.length
      ? table(["Computer", "Joined", "Last used", ""], computers.map((c) => [
          c.name, c.paired_at.slice(0, 10),
          c.last_seen_at ? c.last_seen_at.slice(0, 16).replace("T", " ") : "not yet",
          h("button", { class: "danger", type: "button", onclick: () => remove(c) }, "Remove")]))
      : empty("No other computers are connected."));
    return computers;
  }
  async function remove(c) {
    if (!confirm(`Remove "${c.name}"? It stops working right away. You can connect it again later.`)) return;
    try {
      await removeComputer(c.id);
      await show();
    } catch (err) {
      showError(box, err);
    }
  }
  return { box, show };
}

export async function render(root) {
  const area = h("div", {});
  const { box, show } = computerList();
  let timers = [];
  const stopTimers = () => { timers.forEach(clearInterval); timers = []; };
  onLeave(stopTimers);

  async function allow() {
    stopTimers();
    const known = new Set((await listComputers()).map((c) => c.id));
    const j = await newJoinCode();
    const countdown = h("p", { class: "muted" });
    fill(area,
      h("p", {}, "On the other computer, open a web browser and go to:"),
      h("p", { class: "big" }, j.address),
      h("p", {}, "Then type this code and a name for that computer:"),
      h("p", { class: "big" }, j.code),
      countdown,
      j.can_connect ? null : note(j.message || "Other computers may not be able to reach this one yet."),
      empty("Don't share the code: it works once, for a short time."));
    const tick = () => {
      const left = j.expires_at - Math.floor(Date.now() / 1000);
      if (left > 0) {
        countdown.textContent = `Works for ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")} more.`;
        return;
      }
      stopTimers();
      fill(area, note("That code has expired. Click \"Allow another computer\" for a new one."));
      show().catch(() => {});
    };
    tick();
    timers.push(setInterval(tick, 1000));
    timers.push(setInterval(async () => {
      try {
        if ((await show()).some((c) => !known.has(c.id))) {
          stopTimers();
          fill(area, h("p", { class: "ok", role: "status" }, "New computer connected"));
        }
      } catch { /* try again in a few seconds */ }
    }, POLL_MS));
  }

  const button = h("button", { class: "primary", type: "button", onclick: () => allow().catch((err) => showError(area, err)) },
    "Allow another computer");
  fill(root,
    card("Use Budget Buddy on another computer",
      h("p", {}, "Another computer on your home network can open Budget Buddy in its web browser. It needs a " +
        "one-time code from this computer. It can do everything except connect phones or other computers."),
      note("Only do this on a home network you trust. Pages travel over your Wi-Fi without extra encryption."),
      button, area),
    card("Connected computers", box));
  await show();
}
