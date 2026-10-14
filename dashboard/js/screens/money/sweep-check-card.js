// Part of the Investments screen: deposit sweep lines not linked to a dividend or trade yet, each with the ones
// nearby in the same account that could be its match and a Link button, plus counts per account that should add
// up. A link made here can be undone right away. Rules: services/investing/sweep_check.py on the server.

import { checkSweeps, linkSweep, unlinkSweep } from "../../api/endpoints.js";
import { fill, h } from "../../dom.js";
import { formatCents } from "../../money.js";
import { reload } from "../../router.js";
import { card, empty, select, table } from "../../widgets.js";
import { gapQuestion, gapText, matchText } from "../../sweep-words.js";

function undoLine(sweepId) {
  const note = h("span", { class: "muted", role: "status" }, " Linked.");
  const undo = h("button", { type: "button", class: "plain", onclick: async () => {
    undo.disabled = true;
    try {
      await unlinkSweep(sweepId);
      await reload();
    } catch (err) {
      note.textContent = ` ${err.message}`;
    }
  } }, "Undo");
  return h("span", {}, note, " ", undo);
}

function linkForm(line) {
  if (!line.matches.length) return h("span", { class: "muted" }, "Nothing nearby in this account to link it to.");
  const pick = select(line.matches.map((m, i) => [i, matchText(m)]), { class: "sweep-pick", "aria-label": `Match for ${line.description}` });
  const message = h("span", { class: "error", role: "alert" });
  const holder = h("span", { class: "inline-form" });
  const button = h("button", { type: "button", class: "primary", onclick: async () => {
    const m = line.matches[Number(pick.value)];
    if (m.gap_cents && !window.confirm(gapQuestion(m))) return;
    button.disabled = true;
    try {
      await linkSweep(line.transaction_id, { kind: m.kind, record_id: m.record_id, confirm: m.gap_cents > 0 });
      fill(holder, undoLine(line.transaction_id));
    } catch (err) {
      message.textContent = ` ${err.message}`;
      button.disabled = false;
    }
  } }, "Link");
  holder.append(pick, button, message);
  return holder;
}

function countsTable(accounts) {
  return table(["Account", "Dividends and trades", "With their sweep", "Sweep lines not linked", ""],
    accounts.map((a) => [a.account_name, a.payments, a.with_sweep, a.free_sweeps, gapText(a) || "Adds up"]),
    [1, 2, 3]);
}

export async function sweepCheckCard() {
  const { accounts, unlinked, suggest_days: days } = await checkSweeps();
  if (!accounts.length) return null;
  return card("Deposit sweeps to check",
    empty("A deposit sweep moves the cash of a dividend or trade in or out of your account. Linked to its dividend " +
      "or trade, it doesn't count as spending, income or something to sort. Budget Buddy links one by itself when " +
      "it says \"sweep\", is in the same account, is for exactly the opposite amount, and comes from a day before to " +
      "three days after. The lines below didn't fit: pick the dividend or trade each one goes with and click Link. " +
      `Dividends and trades up to ${days} days away are offered, the same amount first.`),
    countsTable(accounts),
    unlinked.length
      ? table(["Date", "Account", "Sweep line", "Amount", "Goes with"], unlinked.map((line) => [
          line.date, line.account_name, line.description, formatCents(line.amount_cents), linkForm(line),
        ]), [3])
      : empty("Every sweep line is linked."));
}
