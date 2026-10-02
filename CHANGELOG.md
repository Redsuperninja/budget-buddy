# Changelog

## Unreleased
- Project scaffold: architecture, roadmap, ADRs, and specialized agent definitions.
- Home Base server skeleton: FastAPI app, settings, data folder, `/api/health`, home-network-only access, tests, and CI.
- Phone app starter: Expo app with bottom tabs (Home, Add Receipt, Taxes, Settings), light/dark theme, money formatting, and mobile CI.
- Server hardening: home-network check now also covers WebSockets, listens on this computer only by default, keeps the data folder private on macOS/Linux, and hides the API docs unless dev mode is on.
