# Orchestrator tick

Run this prompt on every tick (today: a session timer at :17 and :47; later: the poller in `docs/poller.md`).

1. **Load state.** Read `state/open-requests.json` and the rules in `rules/`.
2. **Trello.** Fetch the notifications of the signed-in member (`GET /1/members/me/notifications`). They cover every board, so no board list is needed. Then re-read the last 3 comments on every Trello card in the ledger. Add each new ask to the ledger.
3. **Slack.** Read new messages in the watched channels (`config/watch.json`, by channel ID, never by name). `conversations.history` returns only top-level messages, so also read the replies of **every thread in those channels with activity in the last 48 hours** (`latest_reply` newer than the last tick), including threads closed in the ledger: a new ask can come inside an old thread.
4. **GitHub.** List the open PRs of the owner in the watched orgs. For new review comments or CI failures, fix them: review the change with Codex before the push, merge the base branch in instead of a rebase, and never force-push.
5. **Work every open ledger item now.** Do its next step. Automate device work first (see `rules/device-automation.md`). Close an item only after the reply with evidence is posted, and set the reactions on the original message (`rules/slack-status-reactions.md`).
6. **Blocked on the owner?** Tell the requester once what is ready and what waits. List the item at the top of every tick output until it is done.
7. **Save** `state/open-requests.json` after each change.
8. **Skip** work that an active Conductor session owns. Read `/Volumes/HD/conductor/workspaces/*` and its transcripts to see that.
9. **Nothing changed:** stay quiet.
