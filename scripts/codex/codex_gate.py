#!/usr/bin/env python3
"""Codex review before every push.

Two modes:

  codex_gate.py review [--base BRANCH] [--dir PATH] [--timeout SECONDS]
      Runs `codex review --base origin/BRANCH` on the current branch and records
      the result for HEAD. A later `git push` of the same HEAD (or of a merge
      commit that does not change the branch diff) is then allowed.
      When Codex answers that the usage limit is reached, it records that
      instead, and pushes are allowed without a review for USAGE_SKIP_HOURS.

  codex_gate.py hook
      PreToolUse hook for the Bash tool (JSON on stdin). It blocks `git push`
      when HEAD has no recorded Codex review, unless the usage-gone window is
      open. Every other command passes at once.

Records live in <git common dir>/codex-reviews/records.jsonl, so all worktrees
of a repo share them. The usage marker is global: ~/.codex-gate/usage-gone.json.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time

USAGE_SKIP_HOURS = float(os.environ.get("CODEX_GATE_USAGE_SKIP_HOURS", "3"))
USAGE_FILE = os.path.expanduser(os.environ.get("CODEX_GATE_USAGE_FILE", "~/.codex-gate/usage-gone.json"))
USAGE_PATTERNS = re.compile(
    r"usage limit|rate[ _-]?limit|quota|insufficient_quota|too many requests|"
    r"\b429\b|hit your (usage )?limit|limit (has been )?reached|try again (at|in) ",
    re.I,
)
SELF = os.path.abspath(__file__)


def git(args, cwd, check=True, timeout=60):
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout.strip()


def store_dir(cwd):
    common = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd)
    d = os.path.join(common, "codex-reviews")
    os.makedirs(d, exist_ok=True)
    return d


def read_records(cwd):
    path = os.path.join(store_dir(cwd), "records.jsonl")
    out = []
    if os.path.exists(path):
        for line in open(path):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def add_record(cwd, rec):
    with open(os.path.join(store_dir(cwd), "records.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


def diff_hash(cwd, base):
    """Hash of the branch diff against origin/<base> (merge-base to HEAD)."""
    mb = git(["merge-base", f"origin/{base}", "HEAD"], cwd)
    raw = subprocess.run(["git", "-C", cwd, "diff", "--binary", mb, "HEAD"],
                         capture_output=True, timeout=120).stdout
    return hashlib.sha256(raw).hexdigest(), len(raw)


def default_base(cwd):
    try:
        r = subprocess.run(["gh", "pr", "view", "--json", "baseRefName", "-q", ".baseRefName"],
                           cwd=cwd, capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    head = git(["symbolic-ref", "-q", "refs/remotes/origin/HEAD"], cwd, check=False)
    return head.rsplit("/", 1)[-1] if head else "main"


def usage_window():
    """Return (open, until) for the usage-gone skip window."""
    try:
        d = json.load(open(USAGE_FILE))
        until = d["time"] + USAGE_SKIP_HOURS * 3600
        return time.time() < until, until
    except Exception:
        return False, 0


def stamp(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------- review mode

def cmd_review(a):
    cwd = os.path.abspath(a.dir)
    git(["rev-parse", "--is-inside-work-tree"], cwd)
    if git(["status", "--porcelain", "--untracked-files=no"], cwd):
        print("Commit your changes first: the review covers committed HEAD only.", file=sys.stderr)
        return 2
    base = a.base or default_base(cwd)
    git(["fetch", "-q", "origin", base], cwd, timeout=180)
    sha = git(["rev-parse", "HEAD"], cwd)
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    dh, size = diff_hash(cwd, base)
    log = os.path.join(store_dir(cwd), f"{sha}.log")
    print(f"Codex review of {branch} ({sha[:9]}) against origin/{base}; log: {log}", flush=True)
    try:
        r = subprocess.run(["codex", "review", "--base", f"origin/{base}"], cwd=cwd,
                           capture_output=True, text=True, timeout=a.timeout)
        out, rc = (r.stdout or "") + (r.stderr or ""), r.returncode
    except subprocess.TimeoutExpired as e:
        out, rc = f"timeout after {a.timeout}s\n{e.stdout or ''}", 124
    open(log, "w").write(out)
    rec = {"sha": sha, "branch": branch, "base": base, "diffhash": dh, "time": time.time()}
    if rc == 0:
        add_record(cwd, {**rec, "result": "reviewed"})
        print(out[-6000:])
        print(f"\nRECORDED: Codex review for {sha[:9]}. Fix real findings before you push; "
              "a new commit needs a new review.")
        return 0
    if USAGE_PATTERNS.search(out):
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        json.dump({"time": time.time(), "repo": cwd, "sha": sha, "message": out[-800:]},
                  open(USAGE_FILE, "w"))
        add_record(cwd, {**rec, "result": "usage-gone"})
        print(out[-1500:])
        print(f"\nUSAGE GONE: Codex usage limit reached. Pushes are allowed without a Codex "
              f"review until {stamp(time.time() + USAGE_SKIP_HOURS * 3600)}. Write "
              "'Codex review skipped: usage limit' in the PR body and review the diff yourself.")
        return 0
    print(out[-3000:], file=sys.stderr)
    print(f"\nCodex review failed (exit {rc}). The push stays blocked.", file=sys.stderr)
    return rc or 1


# ------------------------------------------------------------------ hook mode

PUSH_RE = re.compile(r"(?:^|[\s;&|(])git\s+((?:-[Cc]\s+\S+\s+)*)push\b([^;&|]*)")
CD_RE = re.compile(r"(?:^|[\s;&|(])cd\s+(\"[^\"]+\"|'[^']+'|[^\s;&|]+)")


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    return 0


def allow_note(note):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": note}}))
    return 0


def push_dir(cmd, m, cwd):
    opts = m.group(1)
    cm = re.search(r"-C\s+(\S+)", opts or "")
    if cm:
        return os.path.expanduser(shlex.split(cm.group(1))[0])
    cds = [c for c in CD_RE.finditer(cmd[:m.start() + 1])]
    if cds:
        d = os.path.expanduser(shlex.split(cds[-1].group(1))[0])
        return d if os.path.isabs(d) else os.path.join(cwd, d)
    return cwd


def cmd_hook():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if "push" not in cmd or "git" not in cmd:
        return 0
    m = PUSH_RE.search(cmd)
    if not m:
        return 0
    args = m.group(2)
    if re.search(r"(^|\s)(--dry-run|-n|--delete|-d|--help|-h|--tags)(\s|$)", args) or \
            re.search(r"(^|\s):\S", args):
        return 0
    if re.search(r"\bgit\s+(-[Cc]\s+\S+\s+)*commit\b", cmd[:m.start()]):
        return deny("Codex gate: this command commits and pushes in one step. Commit first, run "
                    f"`{SELF} review` on the new HEAD, then push in a separate command.")
    cwd = push_dir(cmd, m, data.get("cwd") or os.getcwd())
    try:
        sha = git(["rev-parse", "HEAD"], cwd, timeout=10)
        branch = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd, timeout=10)
        if not git(["remote"], cwd, timeout=10):
            return 0
    except Exception:
        return 0  # not a repo here: let git report its own error
    recs = read_records(cwd)
    if any(r.get("sha") == sha and r.get("result") == "reviewed" for r in recs):
        return 0
    mine = [r for r in recs if r.get("branch") == branch and r.get("result") == "reviewed"]
    if mine:
        try:
            dh, _ = diff_hash(cwd, mine[-1]["base"])
            if dh == mine[-1]["diffhash"]:
                return 0  # e.g. a merge of the base branch that leaves the branch diff unchanged
        except Exception:
            pass
    open_, until = usage_window()
    if open_:
        return allow_note(f"Codex gate: no Codex review for {sha[:9]}, but the Codex usage limit "
                          f"was reached; pushes are allowed without a review until {stamp(until)}. "
                          "Write 'Codex review skipped: usage limit' in the PR body.")
    return deny(f"Codex gate: no Codex review recorded for HEAD {sha[:9]} on {branch}. Run "
                f"`{SELF} review --dir {cwd}` (add `--base <branch>` if the PR base is not the "
                "default), fix real findings, commit, review again if HEAD changed, then push. "
                "If Codex reports its usage limit, the script records that and pushes are allowed "
                f"for {USAGE_SKIP_HOURS:g} h.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)
    r = sub.add_parser("review")
    r.add_argument("--base")
    r.add_argument("--dir", default=".")
    r.add_argument("--timeout", type=int, default=1500)
    sub.add_parser("hook")
    a = p.parse_args()
    if a.mode == "hook":
        try:
            return cmd_hook()
        except Exception as e:  # never break unrelated Bash calls
            print(f"codex gate hook error: {e}", file=sys.stderr)
            return 0
    return cmd_review(a)


if __name__ == "__main__":
    sys.exit(main())
