# Roadmap

Each line is planned as **one small pull request**. Owner = the specialized agent that leads it
(see [WORKFLOW.md](WORKFLOW.md)).

## Phase 1: Foundation
- [x] 1. Repo scaffold, docs, agent definitions — *architect*
- [x] 2. Home Base skeleton: FastAPI app, config, data folder, health check, tests, CI — *backend-engineer*
- [x] 3. Database layer: SQLAlchemy models + Alembic migrations, money-in-cents helpers — *backend-engineer*
- [ ] 4. Encryption at rest: keyring master key, encrypted file storage — *backend-engineer* + *security-reviewer*

## Phase 2: Getting data in
- [ ] 5. Accounts + transactions API (manual entry) — *backend-engineer*
- [ ] 6. Bank CSV import (checking/savings) with column mapping — *backend-engineer*
- [ ] 7. Paychecks API — *backend-engineer* + *finance-tax-expert*
- [ ] 8. Receipts API: encrypted photo upload, details, optional OCR — *backend-engineer*
- [ ] 9. Auto-categorization rules — *backend-engineer* + *finance-tax-expert*

## Phase 3: Budget & taxes
- [x] 9b. Tax-year reference data (2025, 2026) — *finance-tax-expert*
- [ ] 10. Budget engine: suggested budget (50/30/20 baseline from real data), targets vs actual — *finance-tax-expert*
- [ ] 11. Charitable donations tracking — *finance-tax-expert*
- [ ] 12. Stock lots & sales: cost basis, short/long-term gains — *finance-tax-expert*
- [ ] 13. Other deductions + yearly tax summary export (CSV/PDF) — *finance-tax-expert*

## Phase 4: Sync
- [ ] 14. Pairing: QR code, one-time code, device tokens, revoke — *backend-engineer* + *security-reviewer*
- [ ] 15. Encrypted sync endpoints: snapshot download, receipt upload — *backend-engineer* + *security-reviewer*
- [ ] 16. Local web dashboard (computer side) — *backend-engineer*

## Phase 5: Phone app
- [x] 17. Expo scaffold, navigation, theme — *mobile-engineer*
- [ ] 18. Pair screen (QR scan, secure key storage) — *mobile-engineer*
- [ ] 19. Dashboard: budget breakdown from snapshot — *mobile-engineer*
- [ ] 20. Receipt capture with offline queue — *mobile-engineer*
- [ ] 21. Sync button + 1–3 day reminder notifications — *mobile-engineer*

## Phase 6: Make it easy
- [ ] 22. One-click Windows start (shortcut / tray), auto-start option — *backend-engineer*
- [ ] 23. Plain-English user guide with screenshots — *docs-writer*
- [ ] 24. Encrypted backup & restore — *backend-engineer* + *security-reviewer*
- [ ] 25. Prep for public release: setup wizard, no personal defaults — *architect*
