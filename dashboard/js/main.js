// Starts the dashboard: the list of screens, in the order of the navigation bar.

import { start } from "./router.js";
import * as accounts from "./screens/accounts.js";
import * as categories from "./screens/categories.js";
import * as connectPhone from "./screens/connect-phone.js";
import * as donations from "./screens/donations.js";
import * as home from "./screens/home.js";
import * as importCsv from "./screens/import.js";
import * as paychecks from "./screens/paychecks.js";
import * as stocks from "./screens/stocks.js";
import * as transactions from "./screens/transactions.js";

start([
  { id: "home", label: "Home", render: home.render },
  { id: "accounts", label: "Accounts", render: accounts.render },
  { id: "transactions", label: "Transactions", render: transactions.render },
  { id: "categories", label: "Categories", render: categories.render },
  { id: "import", label: "Import bank file", render: importCsv.render },
  { id: "phone", label: "Connect phone", render: connectPhone.render },
  { id: "paychecks", label: "Paychecks", render: paychecks.render },
  { id: "donations", label: "Donations", render: donations.render },
  { id: "stocks", label: "Stocks", render: stocks.render },
]);
