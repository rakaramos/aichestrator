Keep the watched Slack channels easy to scan: a short headline in the channel, the details in its thread.

- **New top-level message:** at most about 5 words, with an emoji that shows the kind of update. Examples: `✅ Widget check: all pass`, `🧪 Fix live on staging`, `👀 Review needed: #123`, `⚠️ iOS build failed`.
- **Details:** post them right away as a reply in the thread of that headline: evidence, tables, links, screenshots, asks and mentions.
- **Reply to a request in a thread:** keep answering inside that thread. Do not repeat the details in the channel.
- Never post a wall of text as a top-level message, also not for a summary or a release note.
- The status reactions in `rules/slack-status-reactions.md` still apply to the original message.

**Why:** on 5 Nov Rafael asked for brief channel messages: walls of text in the channel make it hard to read.

**How to apply:** with fab-mcp `slack_write`, send `post_message` with only the headline, take its `ts`, then send `reply` with `thread_ts` set to that `ts` for the details. Applies to every channel in `config/watch.json` and to DMs.
