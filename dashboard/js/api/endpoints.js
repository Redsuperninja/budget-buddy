// Everything the dashboard asks of the Home Base: one named function per route, and the only file
// with URL strings. Screens call these; they never build addresses themselves.

import { api } from "./client.js";

const LOCAL = "/api/local";

// Accounts
export const setAccountBalance = (id, json) => api("POST", `${LOCAL}/accounts/${id}/balance`, { json });
export const listAccounts = () => api("GET", `${LOCAL}/accounts`);
export const createAccount = (json) => api("POST", `${LOCAL}/accounts`, { json });

// Categories and the monthly summary
export const listCategories = () => api("GET", `${LOCAL}/categories`);
export const createCategory = (json) => api("POST", `${LOCAL}/categories`, { json });
export const updateCategory = (id, json) => api("PATCH", `${LOCAL}/categories/${id}`, { json });
export const monthlySummary = (month) => api("GET", `${LOCAL}/summary/monthly?month=${month}`);
export const monthlyTrend = (end) => api("GET", `${LOCAL}/summary/trend?end=${end}&months=12`);
export const getBudgetPlan = () => api("GET", `${LOCAL}/budget/plan`);
export const saveBudgetPlan = (json) => api("PUT", `${LOCAL}/budget/plan`, { json });
export const budgetSuggestion = (month) => api("GET", `${LOCAL}/budget/suggestion?month=${month}`);
export const applySuggestion = (json) => api("POST", `${LOCAL}/budget/suggestion/apply`, { json });

// Auto-sort rules ("description contains ..." -> category)
export const listRules = () => api("GET", `${LOCAL}/category-rules`);
export const createRule = (json) => api("POST", `${LOCAL}/category-rules`, { json });
export const deleteRule = (id) => api("DELETE", `${LOCAL}/category-rules/${id}`);
export const applyRules = () => api("POST", `${LOCAL}/category-rules/apply`);

// Transactions (params: URLSearchParams)
export const listTransactions = (params) => api("GET", `${LOCAL}/transactions?${params}`);
export const createTransaction = (json) => api("POST", `${LOCAL}/transactions`, { json });
export const updateTransaction = (id, json) => api("PATCH", `${LOCAL}/transactions/${id}`, { json });
export const matchTransfers = () => api("POST", `${LOCAL}/transactions/match-transfers`);
export const markPersonalGift = (id) => api("POST", `${LOCAL}/transactions/${id}/personal-gift`);

// Bank file import (query: already-encoded text; bytes: the CSV file)
const csv = (accountId) => `${LOCAL}/accounts/${accountId}/csv-import`;
const sendCsv = (path, bytes) => api("POST", path, { body: bytes, contentType: "text/csv" });
export const previewCsv = (accountId, query, bytes) => sendCsv(`${csv(accountId)}/preview?${query}`, bytes);
export const importCsv = (accountId, query, bytes) => sendCsv(`${csv(accountId)}?${query}`, bytes);

// Phones
export const listDevices = () => api("GET", `${LOCAL}/devices`);
export const revokeDevice = (id) => api("POST", `${LOCAL}/devices/${id}/revoke`);
export const startPairing = () => api("POST", `${LOCAL}/pairing`);

// Paychecks
export const listPaychecks = (year) => api("GET", `${LOCAL}/paychecks?year=${year}`);
export const paycheckSummary = (year) => api("GET", `${LOCAL}/paychecks/summary?year=${year}`);
export const payDeposits = (year) => api("GET", `${LOCAL}/paychecks/deposits?year=${year}`);
export const createPaycheck = (json) => api("POST", `${LOCAL}/paychecks`, { json });

// Donations
export const listDonations = (year) => api("GET", `${LOCAL}/donations?tax_year=${year}`);
export const donationSummary = (year) => api("GET", `${LOCAL}/donations/summary/${year}`);
export const createDonation = (json) => api("POST", `${LOCAL}/donations`, { json });
export const deleteDonation = (id) => api("DELETE", `${LOCAL}/donations/${id}`);

// Dividends found in your transactions, with their deposit sweeps
export const listDividends = (year) => api("GET", `${LOCAL}/dividends/${year}`);
export const findDividends = () => api("POST", `${LOCAL}/dividends/find`);
export const dismissDividend = (id) => api("POST", `${LOCAL}/dividends/${id}/dismiss`);

// Other deductions and the yearly tax summary
export const listDeductions = (year) => api("GET", `${LOCAL}/deductions?tax_year=${year}`);
export const createDeduction = (json) => api("POST", `${LOCAL}/deductions`, { json });
export const deleteDeduction = (id) => api("DELETE", `${LOCAL}/deductions/${id}`);
export const taxSummary = (year) => api("GET", `${LOCAL}/tax-summary/${year}`);
// A link target, not a fetch: the browser downloads the file itself.
export const taxExportUrl = (year) => `${LOCAL}/tax-summary/${year}/export.csv`;

// Stocks
export const listLots = () => api("GET", `${LOCAL}/stocks/lots`);
export const createLot = (json) => api("POST", `${LOCAL}/stocks/lots`, { json });
export const listSales = () => api("GET", `${LOCAL}/stocks/sales`);
export const createSale = (json) => api("POST", `${LOCAL}/stocks/sales`, { json });
export const stockGains = (year) => api("GET", `${LOCAL}/stocks/gains/${year}`);
export const stockHoldings = () => api("GET", `${LOCAL}/stocks/holdings`);
export const setStockPrice = (json) => api("POST", `${LOCAL}/stocks/prices`, { json });
export const priceFeed = () => api("GET", `${LOCAL}/price-feed`);
export const savePriceFeed = (json) => api("PUT", `${LOCAL}/price-feed`, { json });
export const refreshPrices = () => api("POST", `${LOCAL}/stocks/prices/refresh`);
// Stock CSV import (query: already-encoded text; bytes: the CSV file)
export const previewStockCsv = (query, bytes) => sendCsv(`${LOCAL}/stocks/import/preview?${query}`, bytes);
export const importStockCsv = (query, bytes) => sendCsv(`${LOCAL}/stocks/import?${query}`, bytes);

// Retirement and HSA contributions against the year's limits
export const retirementLimits = (year) => api("GET", `${LOCAL}/retirement/${year}`);

// Other computers on the home network (ADR-0009)
export const newJoinCode = () => api("POST", `${LOCAL}/remote-computers/join-code`);
export const listComputers = () => api("GET", `${LOCAL}/remote-computers`);
export const removeComputer = (id) => api("POST", `${LOCAL}/remote-computers/${id}/remove`);
export const joinThisComputer = (json) => api("POST", "/api/remote/join", { json });
