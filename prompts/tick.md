# Orchestrator tick

Run this prompt on every tick (every 10 minutes: today a session timer, later: the poller in `docs/poller.md`).

**The 10 minutes hold during other work too.** The session timer fires only while the session is idle. When interactive work (a device test, a build, a review) runs longer than 10 minutes, stop between its steps at least every 10 minutes and run steps 2 to 4. Keep the time of the last check in `state/cursor.json` (local, never committed), and read Slack and Trello from that time, not from a fixed point.

**Keep this checkout on `main`.** The tick reads its prompt and rules from this folder, so a feature branch here runs an old prompt. Make repo changes in a worktree (`git worktree add`), never by a checkout here.

1. **Load state.** Read `state/open-requests.json` (local and git-ignored; start it as `[]` if missing) and the rules in `rules/`.
2. **Trello.** Fetch the notifications of the signed-in member (`GET /1/members/me/notifications`). They cover every board, so no board list is needed. Then re-read the last 3 comments on every Trello card in the ledger. Add each new ask to the ledger.
3. **Slack.** Read new messages in the watched channels (`config/watch.json`, by channel ID, never by name). `conversations.history` returns only top-level messages, so also read the replies of **every thread in those channels with activity in the last 48 hours** (`latest_reply` newer than the last tick), including threads closed in the ledger: a new ask can come inside an old thread.
   - The fab-mcp `conversations_history` result has `reply_count` but no `latest_reply`. So keep a map `thread_reply_counts` (channel → thread `ts` → count) in `state/cursor.json`. On each tick, read the history of the last 48 hours, compare each thread's `reply_count` with the map, read `conversations_replies` for every thread whose count went up, then save the new counts. Reading only the top-level messages misses replies in threads.
   - Read **every** channel in `config/watch.json`, the DMs included. Keep one cursor per channel, `slack_<channel ID>`, in `state/cursor.json`. A channel without a cursor gets the last 48 hours read, then its cursor. After each tick, every watched channel has a cursor that is not older than that tick.
   - The GitHub notification bot DM is read only. Each review request or mention in it is a new request: handle it as below. `scripts/github/pr-activity.py` (step 4) lists the same asks from GitHub, so a missed bot message is still caught.
   - **New request → loop now.** For each new request (a new top-level ask, or a new ask inside a thread), add the ⏳ reaction, add the ledger item, and start its detached loop on this tick. Follow `rules/request-loops.md`. A reaction alone does not handle a request.
4. **GitHub.** List the open PRs of the owner in the watched orgs. For new review comments or CI failures, fix them: review the change with Codex before the push, merge the base branch in instead of a rebase, and never force-push.
   - Read the reviews, review comments and checks of **every open PR of the owner on each tick**, not only of PRs new since the last tick. A PR added to the ledger a minute after it opened gets its bot reviews later.
   - Run `scripts/github/pr-activity.py <last tick time>`. It lists every new review, review thread comment and PR comment from someone other than the owner, and every check that failed since then, on all open PRs of the owner. Act on each line. Do not limit the check to PRs in the ledger: a human review on an older PR counts too.
   - A `REVIEW-REQ` or `MENTION` line with no ledger item is a new request: add the ledger item and start its review loop on this tick (`rules/request-loops.md`). `REVIEW-REQ` lines repeat on each tick until the owner reviews the PR, so check the ledger first.
   - Do not stop to ask before you babysit a PR. Address the review comments, fix CI, push, and reply on the threads, then report what you did.
   - **Merge the owner's PR when it is ready.** Ready means: GitHub reports it mergeable (`mergeStateStatus` is `CLEAN`), every required check passes, no review asks for changes on the head commit, and no thread is unresolved. Merge with the repo's default method, then report the merge. When a stale bot review blocks the merge although its finding is fixed, ask the bot to re-review the head commit, or resolve the thread with a reply that names the fix.
   - Merge stacked PRs in their stated order. Run manual checks (for example, a device test) on the merged build.
   - Ask the owner only before a production deploy.
   - A PR that an **active** session of the owner still works on belongs to that session: leave it. When that session is idle or gone, babysit the PR here.
   - **Review requests:** when the owner is a requested reviewer, review the change without asking first. The orchestrator acts as the owner's GitHub account.
     - Findings that must change: post them in a review with `REQUEST_CHANGES` (or `COMMENT` for questions and nits only).
     - No blocking findings: `APPROVE` the head commit, with a short summary of what was checked. Do not stop at a comment: an author waiting on the owner's review is blocked until it is approved.
     - Re-review on each new head the author pushes, and approve once the findings are fixed.
   - After long interactive work, run a tick before you end the turn.
5. **Work every open ledger item now.** Do its next step. Check that each item's loop still runs, and restart a stopped loop from its `PROGRESS.md` (`rules/request-loops.md`). Automate device work first (see `rules/device-automation.md`). Close an item only after the reply with evidence is posted, and set the reactions on the original message (`rules/slack-status-reactions.md`). Every Slack post follows `rules/slack-message-format.md`: a headline of about 5 words in the channel, the details in its thread.
   - **Done items reply on their own.** When an item from a watched channel is done (the evidence exists: a merged PR, a passing test run, a commit, a published page), post the result reply in the request's thread at once, set `white_check_mark`, and close the item. The owner gave standing approval for these completion replies; do not wait for an OK. This covers results that a detached session or loop sends back to this session.
   - **Still ask first** for anything that is not a completion reply: a new top-level ask to a person, a reply that commits the owner to new work, a production deploy or release, and any post outside the watched channels. Never post in a DM.
6. **Blocked on the owner?** Tell the requester once what is ready and what waits. List the item at the top of every tick output until it is done.
7. **Save** `state/open-requests.json` after each change. It is local state: never commit it.
8. **Skip** work that an active Conductor session owns. Read `/Volumes/HD/conductor/workspaces/*` and its transcripts to see that.
9. **Nothing changed:** stay quiet.
