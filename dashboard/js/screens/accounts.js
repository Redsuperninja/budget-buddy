// Accounts: the list with balances, matching a balance to the bank, and adding a new one.

import { createAccount, listAccounts } from "../api/endpoints.js";
import { fill } from "../dom.js";
import { optionalText } from "../fields.js";
import { form } from "../form.js";
import { ACCOUNT_KINDS, kindLabel } from "../labels.js";
import { formatBalance } from "../money.js";
import { reload } from "../router.js";
import { card, empty, table } from "../widgets.js";
import { balanceCard } from "./account-balance.js";

export async function render(root, options) {
  const accounts = await listAccounts();
  fill(root,
    card("Accounts", accounts.length
      ? table(["Name", "Type", "Bank", "Balance", "Transactions"],
          accounts.map((a) => [a.name, kindLabel(a.kind), a.institution || "",
            formatBalance(a.balance_cents, a.kind), a.transaction_count]), [3, 4])
      : empty("No accounts yet.")),
    accounts.length ? balanceCard(accounts, options.balanceDone) : null,
    card("Add an account",
      form([
        { name: "name", label: "Name", required: true, maxlength: 100, placeholder: "Everyday checking" },
        { name: "kind", label: "Type", options: ACCOUNT_KINDS },
        { name: "institution", label: "Bank or company (optional)", maxlength: 100 },
      ], "Add account", async (v) => {
        await createAccount({ name: v.name, kind: v.kind, institution: optionalText(v.institution) });
        await reload();
      })),
  );
}
