# Code and docs conventions: small files, no repetition

Budget Buddy is read by people and by AI agents. Small, focused files are faster for both: an agent reads
only what it needs, and a developer finds things by file name. Every agent follows these rules, and
reviewers check them.

## Code

- **One job per file.** A module, component or screen does one thing, and its name says what. Aim for
  under ~300 lines. When a file grows past that, split it along its jobs as part of the change.
- **Don't repeat yourself.** Before writing a helper, search for an existing one and reuse it. When the
  same logic or UI shows up a second time, move it into a shared helper instead of copying it.
- **Shared code lives in one obvious place:**
  - Server: business logic in `services/` (one module per area), request/response shapes in `schemas/`,
    small cross-cutting helpers next to what uses them (e.g. `app/crypto/`, `app/bodylimit.py`).
  - Web dashboard (`server/app/dashboard/`): one module per screen, plus shared modules for API calls,
    building the page, money, dates and labels.
  - Phone (`mobile/src/`): screens in `app/`, reusable UI in `components/`, pure logic in `lib/`,
    sync in `sync/`.
- **Short functions with clear names** over comments explaining long ones. A file starts with a one-line
  comment saying what it's for.
- **Refactor as you go, in scope.** Tidy the code you touch. Large clean-ups of unrelated code go in their
  own `chore/` branch.

## Docs

- **One topic per file**, aim for under ~200 lines. Long documents become a short index page that links
  to topic files (for example `docs/architecture/sync.md` linked from `docs/ARCHITECTURE.md`).
- **Say each fact once** and link to it instead of repeating it. The sync wire format lives only in
  `docs/api/sync-contract.md`; tax numbers live only in the per-year data files.
- User guides in `docs/guide/` stay one task per page.
