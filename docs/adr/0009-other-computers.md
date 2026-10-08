# ADR-0009: Using Budget Buddy from another computer on the home network

**Status:** Accepted, 2026-10-08 (built in roadmap 16d).

## Context
The dashboard and its `/api/local/...` API answer only the computer Budget Buddy runs on (loopback peer,
[ADR-0002](0002-wifi-qr-sync.md), [security.md](../dev/architecture/security.md)). There is no login: being on this
computer *is* the permission. The owner wants to open the dashboard from another computer in the house too.

| Option | Safety | Effort |
| --- | --- | --- |
| Remote Desktop to the Budget Buddy computer | Best: nothing changes | None, but clumsy |
| A password any computer on the network can type | A weak password exposes everything; guessable | Small |
| **Pair each computer once, like a phone** | A one-time code shown on the Budget Buddy computer; each computer can be removed | Medium |

## Decision
**Pair each computer with a one-time code, like a phone** (the owner's choice).
- **Off until used.** On the Budget Buddy computer, Devices, Other computers, **Allow another computer** makes an
  8-character code (32-letter alphabet without look-alikes, about 40 bits) that works once for 10 minutes. Only its
  SHA-256 is kept, in memory, never in the database or a log. Five wrong tries end it; joining is rate-limited per
  address. A new code cancels the old one.
- **Joining.** The other computer opens the address shown (`http://<home-network address>:<port>/`) and types the
  code and a name. The Home Base answers with a random 32-byte token in a cookie (`HttpOnly`, `SameSite=Strict`,
  `Path=/`, kept about a year) and keeps only its SHA-256 (table `remote_computers`).
- **What a joined computer may do:** everything the dashboard does, **except** pair phones, allow or remove
  computers, or read the scripts' CSRF token (`/api/local/pairing`, `/api/local/devices`,
  `/api/local/remote-computers`, `/api/local/csrf-token`). Those stay on the Budget Buddy computer, so a lost
  laptop can't let more devices in.
- **Same rules as the local page:** Host must be the home-network address, private addresses only, and writes need
  `Origin: http://<home-network address>:<port>` plus the per-run CSRF token, which the page only gets once the
  cookie is valid. Someone who hasn't joined only sees the join page.
- **Removing** a computer (on the Budget Buddy computer) deletes its token hash; it stops working at once.
- **The home-network listener** stays open while a code is live or a computer is joined, just as for phones.

## Consequences
- **Plain HTTP on the home network.** Unlike phone sync (encrypted by the app), a browser talks plain HTTP, so
  someone who can watch the Wi-Fi traffic could read the pages or copy the cookie. The guide says to use it only on
  a home network you trust, with a strong Wi-Fi password, and to remove computers you no longer use. HTTPS with a
  self-signed certificate would mean browser warnings; it can come later.
- Cookies aren't separated by port, so another web app on the same computer address could see the cookie. Budget
  Buddy's computer is the user's own; noted, not fixed.
- The Windows Firewall rule for **Private networks** that phones need also lets other computers in.
