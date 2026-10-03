# Changelog

## Unreleased
- Project scaffold: architecture, roadmap, ADRs, and specialized agent definitions.
- Home Base server skeleton: FastAPI app, settings, data folder, `/api/health`, home-network-only access, tests, and CI.
- Phone app starter: Expo app with bottom tabs (Home, Add Receipt, Taxes, Settings), light/dark theme, money formatting, and mobile CI.
- Server hardening: home-network check now also covers WebSockets, listens on this computer only by default, keeps the data folder private on macOS/Linux, and hides the API docs unless dev mode is on.
- Tax-year reference data for 2025 and 2026 (brackets, standard deduction, charitable, HSA, retirement, SALT, FICA limits) with IRS sources and a validating loader. See `docs/tax-data.md`.
- Database layer: SQLite database in the data folder with tables for accounts, transactions, categories, paychecks, receipts, donations, stocks, deductions, and devices; it sets itself up and updates automatically on start, comes with a starter set of budget categories, and stores all money as whole cents.
- Sync API contract v1: the exact rules for how the phone and the computer pair and sync, with test examples both sides can check (ADR-0004).
- Phone Home dashboard: this month's income, spending, what's left, and savings rate; Needs / Wants / Savings bars you can tap to see categories; recent activity; and a Taxes summary. Shows clearly labeled sample data until the phone is connected.
