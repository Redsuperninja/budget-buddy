// Starts the dashboard: the sections of the navigation bar and the pages inside each, in order. Another
// computer that hasn't joined yet (no CSRF token in the page) sees only the join page (ADR-0009).

import { start } from "./router.js";
import { addThemePicker } from "./theme-picker.js";
import * as accounts from "./screens/accounts.js";
import * as categories from "./screens/categories.js";
import * as connectPhone from "./screens/connect-phone.js";
import * as donations from "./screens/donations.js";
import * as home from "./screens/home.js";
import * as importCsv from "./screens/import.js";
import * as join from "./screens/join.js";
import * as otherComputers from "./screens/other-computers.js";
import * as paychecks from "./screens/paychecks.js";
import * as plan from "./screens/plan.js";
import * as rules from "./screens/rules.js";
import * as stocks from "./screens/stocks.js";
import * as taxes from "./screens/taxes.js";
import * as transactions from "./screens/transactions.js";

// Connecting phones and computers only works on the Budget Buddy computer itself.
const onThisComputer = ["127.0.0.1", "localhost", "[::1]"].includes(location.hostname);
const joinedOrLocal = document.querySelector('meta[name="csrf-token"]').content !== "";

const sections = [
  { id: "home", label: "Home", pages: [{ id: "home", label: "Home", render: home.render }] },
  { id: "money", label: "Money", pages: [
    { id: "transactions", label: "Transactions", render: transactions.render },
    { id: "accounts", label: "Accounts", render: accounts.render },
    { id: "import", label: "Import bank file", render: importCsv.render },
    { id: "rules", label: "Auto-sort", render: rules.render },
  ] },
  { id: "budget", label: "Budget", pages: [
    { id: "categories", label: "Categories", render: categories.render },
    { id: "plan", label: "Suggested budget", render: plan.render },
  ] },
  { id: "tax", label: "Taxes", pages: [
    { id: "taxes", label: "Tax summary", render: taxes.render },
    { id: "donations", label: "Donations", render: donations.render },
    { id: "paychecks", label: "Paychecks", render: paychecks.render },
    { id: "stocks", label: "Stocks", render: stocks.render },
  ] },
  { id: "devices", label: "Devices", pages: [
    { id: "phone", label: "Connect phone", render: connectPhone.render },
    { id: "computers", label: "Other computers", render: otherComputers.render },
  ] },
];

addThemePicker();
if (joinedOrLocal) start(onThisComputer ? sections : sections.filter((s) => s.id !== "devices"));
else join.render(document.getElementById("view"));
