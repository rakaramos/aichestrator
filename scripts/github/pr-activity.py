#!/usr/bin/env python3
"""List new reviews, review comments and PR comments on every open PR of the owner since a time.

Usage: pr-activity.py <since ISO-8601, e.g. 2026-11-06T12:00:00Z>
Reads the owner and orgs from config/watch.json. Needs `gh` signed in.
Prints one line per new item from someone other than the owner, and one line per PR whose checks failed since then.
Prints nothing when there is no news, so the tick can stay quiet.
"""
import json, os, subprocess, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Bot comments that only report state (a summary, preview controls, review bookkeeping). Anything else from a bot is news.
STATUS_MARKERS = (
    "<!-- forge:preview-controls",
    "<!-- codefox-request:",
    "<!-- codefox-state:",
    "<!-- This is an auto-generated comment: summarize by coderabbit.ai -->",
)


def gh(*args):
    out = subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=True).stdout
    return json.loads(out) if out.strip() else []


def at(stamp):
    """A timezone-aware time from an ISO-8601 string ('Z' or an offset); None for a missing stamp."""
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else None


def after(stamp, since):
    t = at(stamp)
    return t is not None and t > since


def gh_all(path):
    """Every page of a list endpoint."""
    pages = gh("--paginate", "--slurp", path)
    return [item for page in pages for item in page]


def main():
    since = at(sys.argv[1])
    if since.tzinfo is None:
        sys.exit("since needs a timezone, for example 2026-11-06T12:00:00Z")
    cfg = json.load(open(os.path.join(ROOT, "config", "watch.json")))
    owner = cfg["owner"]["github"]
    for org in cfg["github_orgs"]:
        q = f"org:{org} is:pr is:open author:{owner}"
        pages = gh("--paginate", "--slurp", "-X", "GET", "search/issues", "-f", f"q={q}", "-f", "per_page=100")
        prs = [item for page in pages for item in page["items"]]
        for pr in prs:
            repo = pr["repository_url"].split("/repos/")[1]
            n = pr["number"]
            ref = f"{repo.split('/')[1]}#{n}"
            for r in gh_all(f"repos/{repo}/pulls/{n}/reviews?per_page=100"):
                if r["user"]["login"] != owner and after(r.get("submitted_at"), since):
                    print(f"REVIEW  {ref} {r['user']['login']} {r['state']} {r['submitted_at']}")
            for c in gh_all(f"repos/{repo}/pulls/{n}/comments?per_page=100"):
                if c["user"]["login"] != owner and after(c["created_at"], since):
                    body = " ".join(c["body"].split())[:120]
                    print(f"THREAD  {ref} {c['user']['login']} {c['path']}:{c.get('line')} {body}")
            for c in gh_all(f"repos/{repo}/issues/{n}/comments?per_page=100"):
                if c["user"]["login"].endswith("[bot]") and any(m in c["body"] for m in STATUS_MARKERS):
                    continue
                if c["user"]["login"] != owner and after(c["created_at"], since):
                    body = " ".join(c["body"].split())[:120]
                    print(f"COMMENT {ref} {c['user']['login']} {body}")
            head = gh(f"repos/{repo}/pulls/{n}")["head"]["sha"]
            runs = [r for page in gh("--paginate", "--slurp", f"repos/{repo}/commits/{head}/check-runs?per_page=100")
                    for r in page.get("check_runs", [])]
            # Only failures that finished after `since`, so an old red PR is reported once, not on every tick.
            failed = sorted({r["name"] for r in runs
                             if r.get("conclusion") in ("failure", "timed_out") and after(r.get("completed_at"), since)})
            statuses = [x for page in gh("--paginate", "--slurp", f"repos/{repo}/commits/{head}/status?per_page=100")
                        for x in page.get("statuses", [])]
            failed += sorted({s["context"] for s in statuses if s["state"] in ("failure", "error") and after(s["updated_at"], since)})
            if failed:
                print(f"CI-FAIL {ref} {head[:8]} {', '.join(failed)}")


if __name__ == "__main__":
    main()
