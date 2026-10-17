// Starts the dashboard: the sections of the navigation bar and the pages inside each, in order. Pages marked
// advanced only get a tab in the All tools view (Settings, View). Another computer
// or phone that hasn't joined yet (no CSRF token in the page) sees only the join page (ADR-0009).

import { start } from "./router.js";
import { addSettingsMenu } from "./settings-menu.js";
import * as accounts from "./screens/money/accounts.js";
import * as categories from "./screens/budget/categories.js";
import * as backups from "./screens/devices/backups.js";
import * as connectPhone from "./screens/devices/connect-phone.js";
import * as donations from "./screens/tax/donations.js";
import * as home from "./screens/home/home.js";
import * as importCsv from "./screens/money/import.js";
import * as importHistory from "./screens/money/import-history.js";
import * as investments from "./screens/money/investments.js";
import * as join from "./screens/devices/join.js";
import * as otherComputers from "./screens/devices/other-computers.js";
import * as paychecks from "./screens/tax/paychecks.js";
import * as plan from "./screens/budget/plan.js";
import * as receipts from "./screens/money/receipts.js";
import * as rules from "./screens/money/rules.js";
import * as stocks from "./screens/tax/stocks.js";
import * as taxes from "./screens/tax/taxes.js";
import * as transactions from "./screens/money/transactions.js";

// Connecting phones and computers only works on the Budget Buddy computer itself.
const onThisComputer = ["127.0.0.1", "localhost", "[::1]"].includes(location.hostname);
const joinedOrLocal = document.querySelector('meta[name="csrf-token"]').content !== "";

const sections = [
  { id: "home", label: "Home", pages: [{ id: "home", label: "Home", render: home.render }] },
  { id: "money", label: "Money", pages: [
    { id: "transactions", label: "Transactions", render: transactions.render },
    { id: "accounts", label: "Accounts", render: accounts.render },
    { id: "investments", label: "Investments", render: investments.render },
    { id: "import", label: "Import files", render: importCsv.render },
    { id: "import-history", label: "Import history", render: importHistory.render, advanced: true },
    { id: "receipts", label: "Receipts", render: receipts.render },
    { id: "rules", label: "Auto-sort", render: rules.render, advanced: true },
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
    { id: "computers", label: "Other devices", render: otherComputers.render },
    { id: "backups", label: "Backups", render: backups.render },
  ] },
];

addSettingsMenu();
if (joinedOrLocal) start(onThisComputer ? sections : sections.filter((s) => s.id !== "devices"));
else join.render(document.getElementById("view"));
