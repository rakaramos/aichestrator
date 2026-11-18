#!/usr/bin/env python3
"""List open ledger items whose request has no visible child session.

Rule (rules/request-loops.md): every open request is owned by a child
session of the orchestrator that the owner can open and steer. A loop
that is a scheduled-task run (hidden), a background agent, or missing
breaks that rule. Ticks cannot fix it, because the app refuses
start_session on automated turns. The first owner turn must fix it.

Usage:
  hidden-loops.py            print the list (exit 1 when it is not empty)
  hidden-loops.py --hook     UserPromptSubmit hook: read the hook JSON on
                             stdin and inject the list as context, only in
                             the orchestrator folder
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "state", "open-requests.json")

CLOSED = {"done", "closed", "merged", "parked", "cancelled", "dropped"}
# Statuses where work is still to do, so a missing loop is a defect.
ACTIVE = {"open", "new", "in_progress"}
# A loop kind the owner cannot open as a session.
NOT_VISIBLE = {"scheduled_task", "agent"}
TICK_PREFIX = "Orchestrator tick:"


def find_problems():
    with open(LEDGER) as f:
        items = json.load(f)
    problems = []
    for item in items:
        status = item.get("status") or ""
        if status in CLOSED:
            continue
        loop = item.get("loop")
        rid = item.get("id") or "(no id)"
        if not loop:
            if status in ACTIVE:
                problems.append((rid, status, "no loop", None))
            continue
        kind = loop.get("kind")
        if kind == "orchestrator":
            # Declared on purpose: the orchestrator itself owns it (for
            # example a thread it only relays). Needs a "reason".
            continue
        if loop.get("hidden") or kind in NOT_VISIBLE:
            what = "hidden scheduled-task run" if (loop.get("hidden") or kind == "scheduled_task") else "background agent"
            problems.append((rid, status, what, loop))
    return problems


def format_list(problems):
    lines = []
    for rid, status, what, loop in problems:
        ref = ""
        if loop:
            bits = [loop.get("id"), loop.get("task"), loop.get("progress")]
            ref = " — " + ", ".join(str(b) for b in bits if b)
        lines.append(f"- {rid} [{status}]: {what}{ref}")
    return "\n".join(lines)


def hook():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    cwd = data.get("cwd") or os.getcwd()
    if os.path.realpath(cwd) != os.path.realpath(ROOT):
        return 0
    problems = find_problems()
    if not problems:
        return 0
    listing = format_list(problems)
    prompt = (data.get("prompt") or "").lstrip()
    if prompt.startswith(TICK_PREFIX):
        text = (
            "ORCHESTRATOR GUARD: these open requests have no visible child session:\n"
            f"{listing}\n"
            "This tick cannot call start_session (automated turn). Put this list at the top "
            "of the tick output with links, and send one PushNotification per new entry "
            "asking the owner to reply 'promote' so an owner turn can start the child sessions."
        )
    else:
        text = (
            "ORCHESTRATOR GUARD — DO THIS FIRST, before answering the message: these open "
            "requests have no visible child session:\n"
            f"{listing}\n"
            "This is an owner turn, so start_session works. For each item: start_session "
            "(initiation 'user_asked', context 'fresh', use_worktree false) with the request "
            "brief plus 'resume from PROGRESS.md'; archive the hidden run and delete its "
            "loop-<id> scheduled task (or stop the agent); set the item's loop to "
            "{kind:'session', id, progress, child_of:<orchestrator session id>}; tell the owner "
            "in one line with a link. Only if the orchestrator itself must own an item, set "
            "loop {kind:'orchestrator', reason}. See rules/request-loops.md."
        )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}))
    return 0


def main():
    if "--hook" in sys.argv:
        return hook()
    problems = find_problems()
    if problems:
        print(format_list(problems))
        return 1
    print("OK: every open request has a visible child session")
    return 0


if __name__ == "__main__":
    sys.exit(main())
