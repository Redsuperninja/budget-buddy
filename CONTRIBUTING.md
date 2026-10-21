# Contributing to Budget Buddy

Thanks for helping. Budget Buddy keeps people's money records private, so please read the rules below before
you change anything.

## Set up

Follow [docs/dev/testing.md](docs/dev/testing.md). It lists the setup steps for each part: the Home Base (the
server, Python), the dashboard (plain web files), the phone app (Expo) and the Windows desktop app.

## Run the tests

- Run the tests for the part you changed first. The commands are in [docs/dev/testing.md](docs/dev/testing.md).
- To run every check at once, as CI does: `python scripts/dev/check_all.py` (on Windows, `py scripts/dev/check_all.py`).
- The full server test suite takes about 14 minutes. Run it once before you send a change.
- Never make a test pass by weakening it or skipping it. If a test is wrong, say why in your pull request.

## Branches and commits

- Make one change per branch, and keep it small (ideally under about 400 changed lines).
- Name the branch with a prefix: `feat/` for a new feature, `fix/` for a bug, `docs/` for documentation, or
  `chore/` for housekeeping. For example, `fix/receipt-upload-message`.
- Never commit to `main`. Changes reach `main` only through a pull request.
- Write commit messages in plain English.

## Rules for every change

- **Never commit real financial data.** That means bank files, account numbers, real transactions, receipt photos,
  tax documents or a database. Use made-up examples in tests and docs.
- **Never commit keys, passwords, tokens or `.env` files.**
- **Money is stored in whole cents**, and dates are written `YYYY-MM-DD`.
- **Update the docs in the same branch.** Tick the item in [docs/ROADMAP.md](docs/ROADMAP.md), add a line to
  [CHANGELOG.md](CHANGELOG.md), and update the developer docs and the user guide ([docs/guide](docs/guide/README.md))
  for anything a user or developer will see. Write user-facing text in plain English.
- **Security and money maths get a second look.** Changes to storage, encryption, pairing, sync, login or uploads
  need a security review. Changes to budget or tax maths need a finance review. The pull request template has the
  checklist.
- Code conventions are in [docs/dev/conventions.md](docs/dev/conventions.md).

## Opening a pull request

1. Push your branch and open a pull request into `main`.
2. Fill in the template. It asks for:
   - **What**: what the change does, in plain English.
   - **Why**: the problem it solves.
   - **How to test**: the steps a reviewer can follow.
   - **Reviewers needed**: tick the security and finance reviews if they apply.
3. Leave the last line of the template as it is. It credits the work and names the owner who reviews it:
   `Built with Claude Code; designed and reviewed by @Redsuperninja.`
4. Don't add co-author or generated-by lines to commit messages.

## Reporting problems

- Bugs and ideas: open an issue with the **Bug report** or **Idea** form. Use made-up data only.
- Security problems: don't open a public issue. Follow [SECURITY.md](SECURITY.md).
- Testers: see [docs/testing/what-to-test.md](docs/testing/what-to-test.md).
