# Changelog

## Unreleased
- Project scaffold: architecture, roadmap, ADRs, and specialized agent definitions.
- Home Base server skeleton: FastAPI app, settings, data folder, `/api/health`, home-network-only access, tests, and CI.
- Phone app starter: Expo app with bottom tabs (Home, Add Receipt, Taxes, Settings), light/dark theme, money formatting, and mobile CI.
- Server hardening: home-network check now also covers WebSockets, listens on this computer only by default, keeps the data folder private on macOS/Linux, and hides the API docs unless dev mode is on.
- Tax-year reference data for 2025 and 2026 (brackets, standard deduction, charitable, HSA, retirement, SALT, FICA limits) with IRS sources and a validating loader. See `docs/tax-data.md`.
- Database layer: SQLite database in the data folder with tables for accounts, transactions, categories, paychecks, receipts, donations, stocks, deductions, and devices; it sets itself up and updates automatically on start, comes with a starter set of budget categories, and stores all money as whole cents.
- Sync API contract v1: the exact rules for how the phone and the computer pair and sync, with test examples both sides can check (ADR-0004).
- Encryption at rest: account numbers, notes, and receipt file names are encrypted in the database, receipt photos can be saved encrypted, the key lives in Windows Credential Manager (or the macOS/Linux equivalent), and a recovery phrase lets you get your data back if that key is lost (ADR-0003).
- Accounts + transactions API for the computer-side dashboard (`/api/local/...`, this computer only): add, edit, and remove accounts and transactions, see account balances, filter and page through transactions, and link transfers between your own accounts. Errors come back as plain-English messages. Other websites open in your browser can't reach it (Host and Origin checks), every route except the phone's is this-computer-only by default, search text stays out of the logs, and transfers, refunds and opening balances follow fixed rules so they never turn into surprise income or spending.
- Phone Home dashboard: this month's income, spending, what's left, and savings rate; Needs / Wants / Savings bars you can tap to see categories; recent activity; and a Taxes summary. Shows clearly labeled sample data until the phone is connected.
