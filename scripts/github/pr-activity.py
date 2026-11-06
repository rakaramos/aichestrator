#!/usr/bin/env python3
"""List new reviews, review comments and PR comments on every open PR of the owner since a time.

Usage: pr-activity.py <since ISO-8601, e.g. 2026-11-06T12:00:00Z>
Reads the owner and orgs from config/watch.json. Needs `gh` signed in.
Prints one line per new item from someone other than the owner, and one line per PR whose checks failed since then.
Prints nothing when there is no news, so the tick can stay quiet.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def gh(*args):
    out = subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=True).stdout
    return json.loads(out) if out.strip() else []


def main():
    since = sys.argv[1]
    cfg = json.load(open(os.path.join(ROOT, "config", "watch.json")))
    owner = cfg["owner"]["github"]
    for org in cfg["github_orgs"]:
        q = f"org:{org} is:pr is:open author:{owner}"
        prs = gh("-X", "GET", "search/issues", "-f", f"q={q}", "-f", "per_page=100")["items"]
        for pr in prs:
            repo = pr["repository_url"].split("/repos/")[1]
            n = pr["number"]
            ref = f"{repo.split('/')[1]}#{n}"
            for r in gh(f"repos/{repo}/pulls/{n}/reviews?per_page=100"):
                if r["user"]["login"] != owner and (r.get("submitted_at") or "") > since:
                    print(f"REVIEW  {ref} {r['user']['login']} {r['state']} {r['submitted_at']}")
            for c in gh(f"repos/{repo}/pulls/{n}/comments?per_page=100"):
                if c["user"]["login"] != owner and c["created_at"] > since:
                    body = " ".join(c["body"].split())[:120]
                    print(f"THREAD  {ref} {c['user']['login']} {c['path']}:{c.get('line')} {body}")
            for c in gh(f"repos/{repo}/issues/{n}/comments?per_page=100"):
                # Bot status comments (summaries, preview controls, review state) carry no ask.
                if c["user"]["login"].endswith("[bot]") and c["body"].lstrip().startswith("<!--"):
                    continue
                if c["user"]["login"] != owner and c["created_at"] > since:
                    body = " ".join(c["body"].split())[:120]
                    print(f"COMMENT {ref} {c['user']['login']} {body}")
            head = gh(f"repos/{repo}/pulls/{n}")["head"]["sha"]
            runs = gh(f"repos/{repo}/commits/{head}/check-runs?per_page=100").get("check_runs", [])
            # Only failures that finished after `since`, so an old red PR is reported once, not on every tick.
            failed = sorted({r["name"] for r in runs
                             if r.get("conclusion") in ("failure", "timed_out") and (r.get("completed_at") or "") > since})
            statuses = gh(f"repos/{repo}/commits/{head}/status").get("statuses", [])
            failed += sorted({s["context"] for s in statuses if s["state"] in ("failure", "error") and s["updated_at"] > since})
            if failed:
                print(f"CI-FAIL {ref} {head[:8]} {', '.join(failed)}")


if __name__ == "__main__":
    main()
