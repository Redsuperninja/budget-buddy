// Accounts: the list with balances, and adding a new one.

import { api } from "../api.js";
import { card, empty, fill, form, table } from "../dom.js";
import { optionalText } from "../forms.js";
import { ACCOUNT_KINDS, kindLabel } from "../labels.js";
import { formatBalance } from "../money.js";
import { reload } from "../router.js";

export async function render(root) {
  const accounts = await api("GET", "/api/local/accounts");
  fill(root,
    card("Accounts", accounts.length
      ? table(["Name", "Type", "Bank", "Balance", "Transactions"],
          accounts.map((a) => [a.name, kindLabel(a.kind), a.institution || "",
            formatBalance(a.balance_cents, a.kind), a.transaction_count]), [3, 4])
      : empty("No accounts yet.")),
    card("Add an account",
      form([
        { name: "name", label: "Name", required: true, maxlength: 100, placeholder: "Everyday checking" },
        { name: "kind", label: "Type", options: ACCOUNT_KINDS },
        { name: "institution", label: "Bank or company (optional)", maxlength: 100 },
      ], "Add account", async (v) => {
        await api("POST", "/api/local/accounts",
          { json: { name: v.name, kind: v.kind, institution: optionalText(v.institution) } });
        await reload();
      }),
      empty("To record a starting balance, add a transaction of type \"Balance adjustment\" on the Transactions page.")),
  );
}
