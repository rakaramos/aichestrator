
A request read once is not handled. The orchestrator keeps a ledger of open requests and works each one until the requester has an answer.

**Why:** on 3 Nov a Sami comment (Midnight Shelf #111 at 14ce3fc) was read and the build installed, but the checks waited on Rafael, nothing was posted to Sami, and later ticks only looked at newer notifications, so it sat for an hour. Rafael asked to fix this.

**How to apply:**
- Ledger file: `state/open-requests.json` (array of {source, card/thread, requester, asked_at, ask, status, next_step, blocked_on}).
- Each tick: (1) read new notifications AND re-read the latest comments on every card/thread in the ledger, (2) add new asks, (3) for every open item do the next step now, (4) close an item only after the reply with evidence is posted.
- Prefer automating device steps (use a phone without a passcode, background the app instead of locking, read app state through the web inspector) before declaring "needs Rafael".
- If an item truly needs Rafael, acknowledge to the requester (what is ready, what waits) and tell Rafael in plain words at the top of the tick output; repeat every tick until done.
- Related: [[orchestrator-watch-list]], [[slack-status-reactions]]
