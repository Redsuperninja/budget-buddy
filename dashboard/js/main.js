// Starts the dashboard: the sections of the navigation bar and the pages inside each, in order. A page's code
// loads only when it is opened (load: dynamic import). Pages marked
// advanced only get a tab in the All tools view (Settings, View). Another computer
// or phone that hasn't joined yet (no CSRF token in the page) sees only the join page (ADR-0009).

import { devicePages, onThisComputer } from "./features.js";
import { start } from "./router.js";
import { addSettingsMenu } from "./settings-menu.js";

const joinedOrLocal = document.querySelector('meta[name="csrf-token"]').content !== "";

const sections = [
  { id: "home", label: "Home", pages: [{ id: "home", label: "Home", load: () => import("./screens/home/home.js") }] },
  { id: "money", label: "Money", pages: [
    { id: "transactions", label: "Transactions", load: () => import("./screens/money/transactions.js") },
    { id: "accounts", label: "Accounts", load: () => import("./screens/money/accounts.js") },
    { id: "investments", label: "Investments", load: () => import("./screens/money/investments.js") },
    { id: "import", label: "Import files", load: () => import("./screens/money/import.js") },
    { id: "import-history", label: "Import history", load: () => import("./screens/money/import-history.js"), advanced: true },
    { id: "receipts", label: "Receipts", load: () => import("./screens/money/receipts.js") },
    { id: "rules", label: "Auto-sort", load: () => import("./screens/money/rules.js"), advanced: true },
  ] },
  { id: "budget", label: "Budget", pages: [
    { id: "categories", label: "Categories", load: () => import("./screens/budget/categories.js") },
    { id: "plan", label: "Suggested budget", load: () => import("./screens/budget/plan.js") },
  ] },
  { id: "tax", label: "Taxes", pages: [
    { id: "taxes", label: "Tax summary", load: () => import("./screens/tax/taxes.js") },
    { id: "donations", label: "Donations", load: () => import("./screens/tax/donations.js") },
    { id: "paychecks", label: "Paychecks", load: () => import("./screens/tax/paychecks.js") },
    { id: "stocks", label: "Stocks", load: () => import("./screens/tax/stocks.js") },
  ] },
  { id: "devices", label: "Devices", pages: devicePages({
    phone: () => import("./screens/devices/connect-phone.js"),
    computers: () => import("./screens/devices/other-computers.js"),
    backups: () => import("./screens/devices/backups.js"),
  }) },
];

addSettingsMenu();
if (joinedOrLocal) start(onThisComputer() ? sections : sections.filter((s) => s.id !== "devices"));
else import("./screens/devices/join.js").then((join) => join.render(document.getElementById("view")));
