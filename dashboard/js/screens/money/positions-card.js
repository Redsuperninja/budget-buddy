// Part of the Investments screen: positions from your broker's file (a snapshot per account), next to what your
// recorded purchases and sales add up to (both ways: symbols the file leaves out are listed too), and importing a
// new positions file (preview first).

import { clearPositions, importPositions, listPositions, previewPositions } from "../../api/endpoints.js";
import { today } from "../../dates.js";
import { fill, h, showError } from "../../dom.js";
import { pickOptions } from "../../fields.js";
import { formatCents } from "../../money.js";
import { reload } from "../../router.js";
import { advanced, card, empty, note, select, table } from "../../widgets.js";

const money = (cents) => (cents === null ? "" : formatCents(cents));

// Your recorded shares on the file's day next to the broker's, and what to look for when they differ.
function recordsCell(p) {
  if (p.matches) return "Same";
  const text = !p.in_file
    ? `${p.recorded_shares} shares, but the broker doesn't list it: a sale may be missing`
    : p.recorded_shares_micro < p.shares_micro
      ? `${p.recorded_shares} shares: fewer than the broker, a purchase may be missing`
      : `${p.recorded_shares} shares: more than the broker, a sale may be missing`;
  return h("span", { class: "bad" }, text);
}

function accountTable(group, year) {
  const problem = h("span", { class: "error", role: "alert" });
  const forget = h("button", { class: "plain", type: "button", onclick: async () => {
    forget.disabled = true;
    try {
      await clearPositions(group.account_id);
      await reload({ year });
    } catch (err) {
      problem.textContent = ` ${err.message}`;
      forget.disabled = false;
    }
  } }, "Forget this file");
  return h("div", {},
    h("h3", {}, `${group.account_name}, as of ${group.as_of}`),
    group.bank_trades_waiting
      ? note(`${group.bank_trades_waiting} trade(s) from your bank file in this account still need their shares. ` +
          "Add them under Stock trades from your bank file below; the check updates as you do.")
      : null,
    table(["Symbol", "Broker says", "Cost", "Value", "Your records"], group.positions.map((p) => [
      p.symbol, p.in_file ? p.shares : "Not in the file", money(p.cost_basis_cents), money(p.value_cents),
      recordsCell(p),
    ]), [2, 3]),
    h("p", {}, h("strong", {}, `Value: ${group.value_cents === null ? "not known for every line" : formatCents(group.value_cents)}`),
      " ", forget, problem));
}

function importCard(accounts, year) {
  const result = h("div", {});
  const accountSelect = select(pickOptions(accounts));
  const asOf = h("input", { type: "date", value: today() });
  const fileInput = h("input", { type: "file", accept: ".csv,text/csv" });
  let bytes = null;
  const query = (extra = {}) =>
    new URLSearchParams({ account_id: accountSelect.value, as_of: asOf.value, ...extra }).toString();

  function showPreview(p) {
    const ok = p.rows.filter((r) => r.status === "ok");
    const skipped = p.rows.filter((r) => r.status === "skipped").slice(0, 10);
    const button = h("button", { class: "primary", type: "button", disabled: !p.positions, onclick: async () => {
      button.disabled = true;
      try {
        await importPositions(query({ file_name: fileInput.files[0].name }), bytes);
        await reload({ year });
      } catch (err) {
        button.disabled = false;
        showError(result, err);
      }
    } }, `Save ${p.positions} position(s)`);
    fill(result,
      h("p", {}, `${p.positions} position(s) found; ${p.skipped} line(s) skipped.`),
      ok.length ? table(["Symbol", "Shares", "Cost", "Value", "Price"], ok.map((r) =>
        [r.symbol, r.shares, money(r.cost_basis_cents), money(r.value_cents), money(r.price_cents)]), [2, 3, 4]) : null,
      skipped.length ? h("div", {}, h("h3", {}, "Skipped lines"),
        table(["Row", "Why"], skipped.map((r) => [r.row_number, r.problem]))) : null,
      empty("Saving replaces this account's earlier positions file."),
      button);
  }

  return card("Import a positions file",
    empty("Download the positions (holdings) file from your broker's website as CSV. It needs Symbol and Quantity " +
      "columns; cost basis, current value and last price are used when there. It shows what you hold and updates " +
      "prices, but never changes your purchases, sales or gains."),
    h("div", { class: "toolbar" },
      h("label", {}, "Account", accountSelect), h("label", {}, "File is from", asOf),
      h("label", {}, "CSV file", fileInput),
      h("button", { class: "primary", type: "button", onclick: async () => {
        try {
          if (!fileInput.files.length) throw new Error("Please choose a CSV file first.");
          bytes = await fileInput.files[0].arrayBuffer();
          showPreview(await previewPositions(query(), bytes));
        } catch (err) { showError(result, err); }
      } }, "Preview")),
    result);
}

export async function positionsCards(accounts, year) {
  const data = await listPositions();
  return [
    data.accounts.length
      ? card("From your broker's positions file", note(data.note), data.accounts.map((g) => accountTable(g, year)))
      : null,
    accounts.length ? advanced(importCard(accounts, year)) : null,  // a power-user tool (All tools view)
  ];
}
