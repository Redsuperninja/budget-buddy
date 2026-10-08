# Other computers on the home network

Design: [ADR-0009](../../adr/0009-other-computers.md). User guide:
[use-on-another-computer.md](../../guide/use-on-another-computer.md).

Code: `services/remote_computers.py` (codes, tokens), `routers/remote_computers.py`, `app/remote_access.py` (which
requests a home-network computer may make, asked by `LocalAccessMiddleware`), table `remote_computers`
(migration 0013). Dashboard: `screens/other-computers.js` (on this computer) and `screens/join.js`.

## Routes

| Route | Who | What |
| --- | --- | --- |
| `POST /api/local/remote-computers/join-code` | This computer | A code (`ABCD-EFGH`, 8 letters from a 32-letter alphabet), the address to open, when it runs out (10 minutes), and whether the home network can reach it. Opens the home-network listener. `no-store`. |
| `GET /api/local/remote-computers` | This computer | Joined computers still allowed in: name, the address it joined from, joined, last used, when it runs out (90 days). |
| `POST /api/local/remote-computers/{id}/remove` | This computer | Clears its token hash; it stops working at once. 204. |
| `POST /api/remote/join` | Home network | `{code, name}`. Needs `Origin: http://<home-network address>:<port>`, no CSRF token (the page has none yet). 10 tries a minute per address; five wrong codes end the code. Sets the `bb_computer` cookie (`HttpOnly`, `SameSite=Strict`, `Path=/`, 400 days). |

Errors: 403 `wrong_code` (wrong, used or expired: one answer for all), 429 `too_many_tries`, 409 `no_home_network`.

## What a home-network computer may do (`app/remote_access.py`)

- Host must be the home-network address (`{ip}:{port}`); any other is refused.
- Without a valid cookie: only `GET /`, `/static/*` and the join route. The page comes without the CSRF token, so
  the dashboard shows only the join form.
- A cookie counts only from the address that joined and within 90 days (`authenticate`). It's read leniently
  (Starlette's cookie parser), and checked in a worker thread so the database never blocks the event loop.
- With a valid cookie: `/api/local/<area>` for the areas in `JOINED_AREAS` only (an allow-list; anything else,
  including pairing, devices, other computers, the scripts' CSRF token and any new area, is 403
  `not_this_computer`). `test_every_dashboard_route_is_classified` fails when a new area isn't classified.
  Writes need `Origin: http://{ip}:{port}` and the per-run CSRF token, which the page now carries.
- The page gets the CSRF token only when the middleware set `dashboard_token_ok` (this computer, or joined).
- Phone routes (`/api/health`, `/api/pair`, `/api/sync/*`) are unchanged.
- Codes live only in memory, tokens only in the database, both as `hash_secret` (`app/crypto/hashing.py`, shared
  with phone tokens and pairing codes); neither is logged.
- The home-network listener stays open while a code is live or a computer is joined
  ([pairing.md](pairing.md)).
