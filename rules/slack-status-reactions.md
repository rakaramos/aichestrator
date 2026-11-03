
Show the status of Slack requests with reactions on the **original** message (the thread parent):

- When a thread reply completes what the message asked for, add `white_check_mark` to the original message.
- When a request is accepted but still waits in the queue (enqueued, scheduled, waiting on a device or a person), add `hourglass_flowing_sand` (⏳) to the original message. The workspace has no custom `loading` emoji (Slack rejects it). When it is done, add `white_check_mark`.

**Why:** Rafael wants to see at a glance in the channel what is done and what is still in progress.

**How to apply:** use fab-mcp `slack_write` `add_reaction` (executes immediately, no preview) with the channel ID and the parent `ts`. Applies to the watched channel in [[orchestrator-watch-list]] and to DMs with requests.
