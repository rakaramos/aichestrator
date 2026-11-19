#!/usr/bin/env python3
"""Compare a saved fab-mcp slack_read result with state/cursor.json.

Usage: tick-diff.py <saved fab-mcp output file> <channel per command index, comma list>
Prints new top-level messages, threads whose reply_count went up, and
non-parent replies. Exit 0 always. Does not write state.
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
raw = json.load(open(sys.argv[1]))
chans = sys.argv[2].split(",")
cur = json.load(open(os.path.join(ROOT, "state", "cursor.json")))
counts = cur.get("thread_reply_counts", {})
for r in raw["data"]["results"]:
    ch = chans[r["index"]]
    data = r.get("data", {}).get("data", {})
    msgs = data.get("messages", [])
    method = r.get("data", {}).get("method", "")
    for m in msgs:
        ts = m["ts"]
        if method.endswith("replies"):
            if m.get("thread_ts") != ts:
                print(f"REPLY {ch} {m.get('thread_ts')} {ts} {m.get('user')}: {m.get('text','')[:300]}")
            continue
        last = cur.get(f"slack_{ch}", "0")
        if ts > last:
            print(f"NEW {ch} {ts} {m.get('user')}: {m.get('text','')[:300]}")
        rc = m.get("reply_count")
        if rc is not None and rc != counts.get(ch, {}).get(ts):
            print(f"THREAD {ch} {ts} {counts.get(ch, {}).get(ts)} -> {rc}")
print("done")
