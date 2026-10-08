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
| `GET /api/local/remote-computers` | This computer | Joined computers still allowed in: name, joined, last used. |
| `POST /api/local/remote-computers/{id}/remove` | This computer | Clears its token hash; it stops working at once. 204. |
| `POST /api/remote/join` | Home network | `{code, name}`. Needs `Origin: http://<home-network address>:<port>`, no CSRF token (the page has none yet). 10 tries a minute per address; five wrong codes end the code. Sets the `bb_computer` cookie (`HttpOnly`, `SameSite=Strict`, `Path=/`, 400 days). |

Errors: 409 `no_join_code` (none, used or expired), 403 `wrong_code`, 429 `too_many_tries`, 409 `no_home_network`.

## What a home-network computer may do (`app/remote_access.py`)

- Host must be the home-network address (`{ip}:{port}`); any other is refused.
- Without a valid cookie: only `GET /`, `/static/*` and the join route. The page comes without the CSRF token, so
  the dashboard shows only the join form.
- With a valid cookie: every dashboard route except `/api/local/pairing`, `/api/local/devices`,
  `/api/local/remote-computers` and `/api/local/csrf-token` (403 `not_this_computer`). Writes need
  `Origin: http://{ip}:{port}` and the per-run CSRF token, which the page now carries.
- Phone routes (`/api/health`, `/api/pair`, `/api/sync/*`) are unchanged.
- Codes live only in memory as SHA-256; tokens only as SHA-256 in the database; neither is logged.
- The home-network listener stays open while a code is live or a computer is joined
  ([pairing.md](pairing.md)).
