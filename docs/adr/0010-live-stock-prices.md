# ADR-0010: Live stock prices from Finnhub, only when turned on

**Status:** Accepted, 2026-10-09 (built in roadmap 12c).

## Context
Holdings were valued at prices people typed in (roadmap 12b). The owner wants the Investments page to show
current prices, refreshed when the page is opened or on a click, not constantly. That needs prices from the
internet: the first time Budget Buddy would talk to an outside service ([ADR-0001](0001-local-first-stack.md):
no third-party calls with user data).

| Option | Notes |
| --- | --- |
| Stooq (free, no sign-up) | The owner's first choice. Now blocks anything that isn't a web browser (a JavaScript check), so it can't be used. |
| Yahoo Finance chart feed (no sign-up) | Works today, but unofficial: not offered for apps and could break or block without warning. |
| **Finnhub, free key** | An official API meant for this. Free plan: 60 requests a minute, near real-time US prices. Needs a free account. |
| Keep typing prices | Nothing leaves the computer, but no refresh. |

## Decision
**Finnhub with the user's own free key** (the owner's choice), as an exception to "no outside calls" with these
limits:
- **Off until turned on**, on the Investments page. Typing prices keeps working either way.
- **Only symbols are sent** (like VTI), one HTTPS request per held symbol, from the Home Base (never the browser,
  so the page's Content-Security-Policy is unchanged). No amounts, accounts, names or anything else.
- **The key** is stored encrypted (`price_feed.api_key`), never returned by the API, and sent only in the
  `X-Finnhub-Token` header, so it never appears in an address or a log.
- **On demand only:** when the Investments page opens and on its Refresh button; never on a timer. A symbol
  fetched in the last minute isn't asked for again, which also keeps within the free limit.
- Each price records where it came from (`you` or `feed`) and when it was fetched, and the page says so.

## Consequences
- Finnhub learns which symbols someone holds and when they look, tied to their Finnhub account. The guide says
  so plainly before they turn it on.
- If Finnhub changes or a key stops working, refresh stops with a plain message and the last prices stay.
- Funds Finnhub doesn't cover (some mutual funds) get no live price; they can still be typed in.
