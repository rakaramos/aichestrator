# Each new request gets its own loop

A new request in a watched channel gets three things **on the tick that first reads it**, before any other work:

1. **Reaction:** add `hourglass_flowing_sand` to the original message (`rules/slack-status-reactions.md`).
2. **Ledger:** add an item with the request ID (for example `SAMI-069`), the channel, the thread `ts`, the ask, and a `loop` field.
3. **Loop:** start a detached loop that owns the request until it is done. Record it in the item's `loop` field: `{kind, id, progress}`.

The owner gave standing approval for these loops. Do not ask first, and do not show a card.

**Why:** on 11 Nov the ticks read new requests and added the reaction (and once, not even that), but no loop started, so nothing happened. Ticks are automated turns, and the app refuses `start_session` on them. Loops started only when the owner typed the request in chat.

## How to start the loop

1. Call `start_session` with `initiation: "user_asked"`, `context: "fresh"`, a full brief (below) and a `background`.
2. If the app refuses it (an automated turn, Remote Control, or an untrusted repository), start the session through a one-time scheduled task. The app starts every scheduled-task run as a new session, also when a tick asks for it:
   - Call `create_scheduled_task` with `taskId: "loop-<request-id>"` (lower case), `fireAt` set to 1 minute from now (ISO 8601 with the local offset), a `description`, and a `prompt` that is the full brief plus the background. The run starts fresh, so the prompt must stand alone.
   - Record `kind: "scheduled_task"` and the task ID in the item's `loop` field.
   - On the next tick, call `list_task_runs` for that task, take the run's session ID, and record it as `kind: "session"` with `hidden: true`. If no run started, call `run_scheduled_task` once.
   - **A scheduled-task run is hidden.** The sidebar shows it only under its task, not as its own row. The app also refuses to pin it, group it or link it to this session, so `list_sessions` with `linked: true` does not list it. Check it with `get_session` by its ID.
   - **Promote it on the next owner turn.** On the first turn that has a message from the owner (a chat message, or a message that arrives during a tick), the app accepts `start_session`. For each open item with `hidden: true`:
     1. Start a new session with `start_session` (`initiation: "user_asked"`, `context: "fresh"`) and the same brief, plus the line "resume from `PROGRESS.md`" and the ID of the hidden run.
     2. Archive the hidden run with `archive_session`, and delete the `loop-<request-id>` scheduled task if it still exists.
     3. Record the new session in the item's `loop` field, without `hidden`.
     4. Tell the owner in one line, with a link to the new session.
   - Until then, list each hidden loop at the top of every tick output, with a link to its session (`[title](#local_<id>)`) and the line "hidden: under the scheduled task `loop-<request-id>`".
3. If the scheduled task also fails, start a background `Agent` with the same brief and `run_in_background: true`. Record `kind: "agent"` and the agent ID. A background agent is the last resort: the owner cannot open, steer or review it as a session.
4. If all of these fail, put the item at the top of the tick output with the reason. Repeat it every tick until a loop runs.

## The brief

- The request ID, the channel and thread `ts`, and the ask in the requester's own words.
- A worktree under `/Volumes/HD/Developer/worktrees/<request-id>-<topic>` and a `PROGRESS.md` there. The loop updates the file after each step, so a new loop can resume from it, and names in it every worktree and scratch folder it creates (the cleanup reads these paths).
- What done looks like, and what needs the owner's yes first: a production deploy or release, a post in the owner's name that is not a completion reply, and a review that the owner must sign.
- Report to the orchestrator session with `SendMessage`. The loop does not post to Slack; the orchestrator replies in the thread.
- The global rules: never push to main or master, never force-push, write in Simplified Technical English.

## Each tick

- For every open item with a `loop`, check that the loop still runs. A `session` loop: `list_sessions` with `linked: true`, or `get_session` by ID for a `hidden: true` loop. An `agent` loop: its task status.
- A `hidden: true` loop: promote it on the first owner turn (see "Promote it on the next owner turn" above). Until then, list it at the top of the tick output.
- A loop that stopped before the item is done: start a new loop with the same brief and the line "resume from `PROGRESS.md`".
- Relay each loop report: completion replies go to the thread at once; asks for the owner go to the top of the tick output.

## When the item is done: close the loop and reclaim disk space

On each tick, after the completion reply is posted and the item is closed, clean up its loop. The owner gave standing approval for this.

1. **Stop and archive the loop.** A `session` loop: when `list_sessions` with `linked: true` shows it idle or done, call `archive_session`. A session that still works or waits for the owner stays. A `scheduled_task` loop: call `delete_scheduled_task` for `loop-<request-id>`. An `agent` loop: nothing to do once it has finished.
2. **Remove its worktrees.** Run, from this repo:

   ```bash
   python3 scripts/loops/cleanup-worktrees.py --allow-local-head --include-plain \
     --from-progress <PROGRESS.md of each closed item> \
     --protect <PROGRESS.md of each open item>
   ```

   First without `--apply` (dry run), then with `--apply`. The script removes only folders directly under `/Volumes/HD/Developer/worktrees` that have no uncommitted change to a tracked file. It never touches a path that an open item's notes name. It copies each `PROGRESS.md` and the review notes next to it into `state/archive/`, deletes the logs next to it, and deletes the Xcode DerivedData of each removed worktree.
3. **Report it in one line** in the tick output: the folders removed, the space reclaimed, and each `KEEP` line with its reason. A `KEEP` for uncommitted changes needs the owner's look; leave it.

So that step 2 finds every folder, each brief tells the loop to name, in its `PROGRESS.md`, every worktree and scratch folder it creates under the worktrees root.
