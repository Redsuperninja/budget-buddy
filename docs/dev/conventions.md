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
    sync in `sync/`, receipts in `receipts/`.
  - Desktop (`desktop/budget_buddy_desktop/`): one module per job (tray, window, starting the Home Base,
    start with Windows); the tray's modules never load the window library.
  - Scripts: one folder per audience (`scripts/testing/`, `scripts/release/`, `scripts/dev/`; everyday ones at the
    top), all Python, standard library only ([ADR-0011](../adr/0011-cross-platform-scripts.md)). The shared local-API
    client is `scripts/testing/_local_api.py`; shared helpers are `scripts/_common.py` and `scripts/_processes.py`.
    What people double-click lives in `launch/` as one-line launchers (`.bat`, `.command`, `.sh`) that call
    `scripts/run-python.*`.
- **Short functions with clear names** over comments explaining long ones. A file starts with a one-line
  comment saying what it's for.
- **Refactor as you go, in scope.** Tidy the code you touch. Large clean-ups of unrelated code go in their
  own `chore/` branch.

## Nothing private in the repo

- **`scripts/dev/check_public.py` must pass** (`check_all.py` and CI run it). It fails on a real-looking email
  address, a home-folder path with a user name, a public IP address, and a tracked `.env`, database,
  `.bbbackup`, key or certificate file, or picture outside `docs/` and `assets/`. Use placeholders instead
  (`you@example.com`, `C:\Users\<you>`, `192.168.1.20`, `203.0.113.7`).
- **Made-up payers and companies in examples**: write "FAKECO" in comments and docs, not a real company. Real
  bank line formats may stay in tests.
- **A justified exception** goes in `scripts/dev/public_allowlist.txt` with a reason on the same line; keep it short.

## Dependencies

- **Add as few as possible.** The dashboard and scripts have none; prefer the standard library. A new package
  needs a reason in its PR and a `security-reviewer` look (licence, maintainers, what it pulls in).
- **Exact versions with hashes:** the server and desktop install from lock files (`requirements-build.txt`,
  `requirements.txt`, `requirements-dev.txt`, `requirements-package.txt`; [ADR-0013](../adr/0013-dependency-lock-files.md)). After changing a `pyproject.toml`, run
  `scripts/dev/lock_dependencies.py` (needs uv) in the same branch; a test fails until you do. Never edit them by hand; review their changes like code.
- **No optional extras we don't use** (the Home Base takes plain `uvicorn`, not `uvicorn[standard]`).
- **GitHub Actions are pinned to a full commit**, with the version in a comment
  (`actions/checkout@<40-character commit> # v7.0.1`), so a moved tag can't change what CI runs.
- **Dependabot** (`.github/dependabot.yml`) opens weekly update PRs (for versions at least a week old) for Actions, the server, the desktop app and the
  phone app. Read what changed before merging; the phone's Expo upgrades are done by hand.

## Docs

- **One topic per file**, aim for under ~200 lines. Long documents become a short index page that links
  to topic files (for example [architecture/sync.md](architecture/sync.md) linked from
  [architecture/README.md](architecture/README.md)).
- **Say each fact once** and link to it instead of repeating it. The sync wire format lives only in
  `docs/api/sync-contract.md` (and its section files); tax numbers live only in the per-year data files;
  environment variables only in [settings.md](settings.md).
- **Where docs go:** people using Budget Buddy read `docs/guide/`; testers trying it with made-up data read
  `docs/testing/`; developers and agents read `docs/dev/` (map: [docs/README.md](../README.md)). Each part's README
  covers how to run and check it, and its layout.
- User guides in `docs/guide/` stay one task per page and are for people only: no environment variables, API
  paths, file or module names, error codes, or code. Tester guides in `docs/testing/` follow the same rules, but may
  have copy-paste commands (both `python3` and `py` where they differ).
