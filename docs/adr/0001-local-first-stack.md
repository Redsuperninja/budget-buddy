# ADR-0001: Local-first stack

**Status:** Accepted, 2026-10-02

## Context
Financial data must stay on the user's computer for now. A phone app is needed for viewing a breakdown and
capturing receipts, on both iPhone and Android, without app-store publishing. The project should be easy to
understand and maintain, and eventually public.

## Decision
- **Home Base:** Python + FastAPI + SQLite (SQLAlchemy/Alembic). Python has strong libraries for CSV handling,
  OCR (Tesseract) and finance math; SQLite is a single file with no database server to install.
- **Phone:** Expo (React Native + TypeScript), runnable through Expo Go on both platforms.
- **No cloud services.** All communication happens over the home network.

## Consequences
- The phone only gets fresh data when on home Wi-Fi (accepted: sync every 1–3 days is enough).
- The Home Base must be running on the computer to sync; we'll provide a one-click start and optional auto-start.
- Expo Go limits us to Expo-supported native modules; acceptable for camera, secure storage, notifications.
