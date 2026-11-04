# Poller (planned)

Today the tick runs from a timer inside one Claude session. That timer stops when the session closes, it sees new items up to 30 minutes late, and every tick costs a model turn even when nothing changed. The plan below splits polling from handling.

| Piece | What it does |
|---|---|
| **Poller**: a plain script started by macOS `launchd` every 3–5 minutes, without Claude | It polls Trello `GET /1/members/me/notifications`, Slack `conversations.history` and `conversations.replies` for the channels in `config/watch.json` and the threads in the ledger, and GitHub `GET /notifications` (review requests, mentions, PR comments). It keeps the last-seen IDs in `state/cursor.json` and appends only new events to `state/inbox.jsonl`. |
| **Wake-up** | When the inbox has new events, it runs `claude -p "$(cat prompts/tick.md)"` in this repo. The run handles the events and the ledger, then empties the inbox. |
| **Ledger** | `state/open-requests.json` (local, git-ignored), unchanged. Items that wait on someone are retried on each run. |

## Open questions

- **Slack token.** The shell has no Slack token today (Slack goes through fab-mcp). The poller needs a user token with `channels:history`, `groups:history` and `im:history`, stored in the macOS Keychain, not in this repo.
- **Questions to the owner.** A headless run cannot ask questions in a terminal. It sends a Slack DM to the owner, then waits for the next run.
- **Webhooks.** Trello and GitHub can push events at once, but that needs a public URL that reaches this Mac. Polling is simpler.
