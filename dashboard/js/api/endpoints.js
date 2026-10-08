// Everything the dashboard asks of the Home Base: one named function per route, and the only file
// with URL strings. Screens call these; they never build addresses themselves.

import { api } from "./client.js";

const LOCAL = "/api/local";

// Accounts
export const listAccounts = () => api("GET", `${LOCAL}/accounts`);
export const createAccount = (json) => api("POST", `${LOCAL}/accounts`, { json });

// Categories and the monthly summary
export const listCategories = () => api("GET", `${LOCAL}/categories`);
export const createCategory = (json) => api("POST", `${LOCAL}/categories`, { json });
export const updateCategory = (id, json) => api("PATCH", `${LOCAL}/categories/${id}`, { json });
export const monthlySummary = (month) => api("GET", `${LOCAL}/summary/monthly?month=${month}`);

// Auto-sort rules ("description contains ..." -> category)
export const listRules = () => api("GET", `${LOCAL}/category-rules`);
export const createRule = (json) => api("POST", `${LOCAL}/category-rules`, { json });
export const deleteRule = (id) => api("DELETE", `${LOCAL}/category-rules/${id}`);
export const applyRules = () => api("POST", `${LOCAL}/category-rules/apply`);

// Transactions (params: URLSearchParams)
export const listTransactions = (params) => api("GET", `${LOCAL}/transactions?${params}`);
export const createTransaction = (json) => api("POST", `${LOCAL}/transactions`, { json });
export const updateTransaction = (id, json) => api("PATCH", `${LOCAL}/transactions/${id}`, { json });

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
export const createPaycheck = (json) => api("POST", `${LOCAL}/paychecks`, { json });

// Donations
export const listDonations = (year) => api("GET", `${LOCAL}/donations?tax_year=${year}`);
export const donationSummary = (year) => api("GET", `${LOCAL}/donations/summary/${year}`);
export const createDonation = (json) => api("POST", `${LOCAL}/donations`, { json });

// Stocks
export const listLots = () => api("GET", `${LOCAL}/stocks/lots`);
export const createLot = (json) => api("POST", `${LOCAL}/stocks/lots`, { json });
export const createSale = (json) => api("POST", `${LOCAL}/stocks/sales`, { json });
export const stockGains = (year) => api("GET", `${LOCAL}/stocks/gains/${year}`);
