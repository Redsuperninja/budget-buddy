# Code and docs conventions: small files, no repetition

Budget Buddy is read by people and by AI agents. Small, focused files are faster for both: an agent reads
only what it needs, and a developer finds things by file name. Every agent follows these rules, and
reviewers check them.

## Code

- **One job per file.** A module, component or screen does one thing, and its name says what. Aim for
  under ~300 lines. When a file grows past that, split it along its jobs as part of the change.
- **Don't repeat yourself.** Before writing a helper, search for an existing one and reuse it. When the
  same logic or UI shows up a second time, move it into a shared helper instead of copying it.
- **Parts never import each other.** `server/`, `dashboard/`, `mobile/`, `desktop/` and `scripts/` talk over
  HTTP (the dashboard, desktop app and scripts through the server's API, the phone through the sync contract; the
  desktop app starts the Home Base as its own program). When two parts need the
  same small helper, each keeps its own copy with its own tests; the no-repetition rule applies inside a part.
- **Shared code lives in one obvious place:**
  - Server: business logic in `services/` (one package per area, one module per job; routers, schemas and
    tests use the same areas, see [server.md](architecture/server.md#areas)), request/response shapes in `schemas/`,
    small cross-cutting helpers next to what uses them (e.g. `app/crypto/`, `app/bodylimit.py`).
  - Web dashboard (`dashboard/js/`): one module per screen in `screens/<section>/` (as in `main.js`), plus shared modules for API calls
    (`api/endpoints.js` holds every route string), building the page, money, dates, labels, and charts
    (`charts/`).
  - Phone (`mobile/src/`): screens in `app/`, reusable UI in `components/`, pure logic in `lib/`,
    sync in `sync/`.
  - Desktop (`desktop/budget_buddy_desktop/`): one module per job (tray, window, starting the Home Base,
    start with Windows); the tray's modules never load the window library.
  - Scripts: the shared local-API client is `scripts/_local_api.py`; shared PowerShell is `scripts/paths.ps1`.
    What people double-click lives in `launch/` as thin `.bat` files that call `scripts/`.
- **Short functions with clear names** over comments explaining long ones. A file starts with a one-line
  comment saying what it's for.
- **Refactor as you go, in scope.** Tidy the code you touch. Large clean-ups of unrelated code go in their
  own `chore/` branch.

## Docs

- **One topic per file**, aim for under ~200 lines. Long documents become a short index page that links
  to topic files (for example [architecture/sync.md](architecture/sync.md) linked from
  [architecture/README.md](architecture/README.md)).
- **Say each fact once** and link to it instead of repeating it. The sync wire format lives only in
  `docs/api/sync-contract.md` (and its section files); tax numbers live only in the per-year data files;
  environment variables only in [settings.md](settings.md).
- **Where docs go:** people using Budget Buddy read `docs/guide/`; developers and agents read `docs/dev/`
  (map: [docs/README.md](../README.md)). Each part's README covers how to run and check it, and its layout.
- User guides in `docs/guide/` stay one task per page and are for people only: no environment variables, API
  paths, file or module names, error codes, or code. Copy-paste PowerShell lines for testers are allowed.
