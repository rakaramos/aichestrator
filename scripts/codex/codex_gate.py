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
# Only messages that say the account's usage or quota is used up. Rate limits,
# 429s and "try again in N seconds" are transient: they keep the push blocked.
USAGE_PATTERNS = re.compile(
    r"usage limit|hit your (usage )?limit|insufficient_quota|exceeded your (current )?quota|"
    r"quota (has been |was )?(exceeded|exhausted|reached)|out of (usage|credits)",
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


def diff_hash(cwd, base, ref="HEAD"):
    """Hash of the branch diff against origin/<base> (merge-base to ref)."""
    mb = git(["merge-base", f"origin/{base}", ref], cwd)
    raw = subprocess.run(["git", "-C", cwd, "diff", "--binary", mb, ref],
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
    prefix = "refs/remotes/origin/"
    return head[len(prefix):] if head.startswith(prefix) else "main"


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

_ARG = r"(?:\"[^\"]*\"|'[^']*'|\S+)"
# git, then any global options (-C dir, -C<dir>, -c k=v, -ck=v, --flag[=v]), then push.
_GLOBAL = r"(?:-[Cc]\s*" + _ARG + r"|--?[\w.-]+(?:=" + _ARG + r")?)"
PUSH_RE = re.compile(r"(?:^|[\s;&|(])git((?:[ \t]+" + _GLOBAL + r")*)[ \t]+push\b([^;&|\n]*)")
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
    """Directory a push runs in: the last `cd` before it, then its own `-C`."""
    d = cwd
    for cdm in CD_RE.finditer(cmd[:m.start() + 1]):  # apply every cd in order
        c = os.path.expanduser(shlex.split(cdm.group(1))[0])
        d = os.path.normpath(c if os.path.isabs(c) else os.path.join(d, c))
    try:
        words = shlex.split(m.group(1) or "")
    except ValueError:
        words = (m.group(1) or "").split()
    i = 0
    while i < len(words):  # only -C changes the directory; -c sets config
        w, c = words[i], None
        if w == "-C" and i + 1 < len(words):
            c, i = words[i + 1], i + 1
        elif w.startswith("-C") and len(w) > 2:
            c = w[2:]
        elif w == "-c":
            i += 1
        if c is not None:
            c = os.path.expanduser(c)
            d = os.path.normpath(c if os.path.isabs(c) else os.path.join(d, c))
        i += 1
    return d


OPTS_WITH_VALUE = {"-o", "--push-option", "--receive-pack", "--exec"}
SKIP_FLAGS = {"--dry-run", "-n", "--help", "-h"}
DELETE_FLAGS = {"--delete", "-d"}
ALL_FLAGS = {"--all", "--mirror", "--branches"}
ALL = "ALL"  # marker: the push uploads many branches at once


def push_remote(args):
    """The remote a push names (first positional, or --repo), else origin."""
    try:
        words = shlex.split(args)
    except ValueError:
        words = args.split()
    i = 0
    while i < len(words):
        w = words[i]
        if w == "--repo" and i + 1 < len(words):
            return words[i + 1]
        if w.startswith("--repo="):
            return w.split("=", 1)[1]
        if w in OPTS_WITH_VALUE:
            i += 2
            continue
        if not w.startswith("-"):
            return w
        i += 1
    return "origin"


def push_sources(args):
    """Return (skip, sources) for one push. sources are the refs it uploads;
    an empty list means the default push (the current branch), and [ALL]
    means a push of many branches (--all, --mirror, a wildcard refspec)."""
    try:
        words = shlex.split(args)
    except ValueError:
        words = args.split()
    positional, i, delete, tags, repo_opt = [], 0, False, False, False
    while i < len(words):
        w = words[i]
        if w in SKIP_FLAGS:
            return True, []
        if w in ALL_FLAGS:
            return False, [ALL]
        if w in DELETE_FLAGS:
            delete = True
        elif w == "--tags":
            tags = True
        elif w == "--repo" or w.startswith("--repo="):
            repo_opt = True
            i += w == "--repo"
        elif w in OPTS_WITH_VALUE:
            i += 1
        elif not w.startswith("-"):
            positional.append(w)
        i += 1
    refspecs = positional if repo_opt else positional[1:]
    if any(r.lstrip("+") == ":" for r in refspecs):
        return False, [ALL]  # the bare ':' refspec pushes every matching branch
    out, j = [], 0
    while j < len(refspecs):  # `tag <name>` is a tag-only refspec
        if refspecs[j] == "tag" and j + 1 < len(refspecs):
            tags, j = True, j + 2
            continue
        out.append(refspecs[j])
        j += 1
    refspecs = out
    if delete:
        return True, []  # every refspec is a deletion
    updates = [r.lstrip("+") for r in refspecs if not r.lstrip("+").startswith(":")]
    if not updates and (tags or refspecs):
        return True, []  # only tags, or only deletions
    if any("*" in r for r in updates):
        return False, [ALL]
    return False, updates  # full refspecs: check_ref reads the source and the destination


def check_ref(cwd, refspec, recs):
    """None when the refspec needs no review or is reviewed, else a short label."""
    src, _, dst = refspec.partition(":")
    full = git(["rev-parse", "--symbolic-full-name", src], cwd, check=False)
    is_tag = src.startswith("refs/tags/") or full.startswith("refs/tags/") or \
        git(["cat-file", "-t", src], cwd, check=False) == "tag"
    if is_tag and (not dst or dst.startswith("refs/tags/") or dst == src):
        return None  # a tag pushed as a tag is not a code change under review
    try:
        sha = git(["rev-parse", "--verify", "-q", f"{src}^{{commit}}"], cwd, timeout=10)
    except Exception:
        return None  # a name git cannot resolve: let git report it
    if any(r.get("sha") == sha and r.get("result") == "reviewed" for r in recs):
        return None
    name = git(["rev-parse", "--abbrev-ref", src], cwd, check=False) or src
    mine = [r for r in recs if r.get("branch") == name and r.get("result") == "reviewed"]
    if mine:
        try:
            dh, _ = diff_hash(cwd, mine[-1]["base"], sha)
            if dh == mine[-1]["diffhash"]:
                return None  # e.g. a merge of the base branch that leaves the branch diff unchanged
        except Exception:
            pass
    return f"{name} ({sha[:9]})"


HEREDOC_RE = re.compile(r"<<-?[ \t]*(['\"]?)(\w+)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)", re.S)
QUOTED_RE = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
MENTIONS_PUSH = re.compile(r"\bgit\b.*\bpush\b", re.S)


def mask_text(cmd):
    """Drop heredoc bodies and quoted strings that only mention `git … push`
    (commit messages, PR bodies, echo/printf text), so they are not read as
    pushes. Quoted paths such as -C '/a b' do not mention git push and stay."""
    cmd = HEREDOC_RE.sub(lambda m: m.group(0).split("\n", 1)[0] + "\n" + m.group(2), cmd)
    return QUOTED_RE.sub(lambda m: "''" if MENTIONS_PUSH.search(m.group(0)) else m.group(0), cmd)


def cmd_hook():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if "push" not in cmd or "git" not in cmd:
        return 0
    cmd = mask_text(cmd)
    base_cwd = data.get("cwd") or os.getcwd()
    missing, dirs = [], []
    for m in PUSH_RE.finditer(cmd):
        skip, srcs = push_sources(m.group(2))
        if skip:
            continue
        if re.search(r"\bgit(?:\s+" + _GLOBAL + r")*\s+commit\b", cmd[:m.start()]):
            return deny("Codex gate: this command commits and pushes in one step. Commit first, "
                        f"run `{SELF} review` on the new HEAD, then push in a separate command.")
        if re.search(r"\(\s*cd\s|\$\(\s*cd\s|`\s*cd\s", cmd[:m.start()]):
            return deny("Codex gate: a `cd` inside a subshell comes before this push, so the hook "
                        "cannot tell the push folder. Use `git -C <absolute path> push …` or a "
                        "plain `cd <path> && git push …`.")
        cwd = push_dir(cmd, m, base_cwd)
        if re.search(r"[$`]", cwd) or not os.path.isdir(cwd):
            return deny(f"Codex gate: cannot resolve the folder of this push ({cwd}). Use a literal "
                        "absolute path (no shell variables) with `cd` or `git -C`, then push.")
        try:
            git(["rev-parse", "HEAD"], cwd, timeout=10)
        except Exception:
            # Fail closed: a push the hook cannot place in a repo is not checked otherwise.
            return deny(f"Codex gate: cannot read the git repo for this push (folder {cwd}). "
                        "Run a plain `git push …` from inside the repo or worktree, or with "
                        "`git -C <absolute path> push …`.")
        if not srcs and (git(["config", "push.default"], cwd, check=False) == "matching" or
                         git(["config", "--get-all", f"remote.{push_remote(m.group(2))}.push"],
                             cwd, check=False)):
            srcs = [ALL]
        if ALL in srcs:
            return deny("Codex gate: this push uploads many or configured branches at once "
                        "(--all, --mirror, a wildcard refspec, push.default=matching or "
                        "remote.<name>.push). Push each branch by name with an explicit refspec, "
                        f"after `{SELF} review` on it.")
        recs = read_records(cwd)
        for src in srcs or ["HEAD"]:
            label = check_ref(cwd, src, recs)
            if label:
                missing.append(label)
                dirs.append(cwd)
    if not missing:
        return 0
    open_, until = usage_window()
    if open_:
        return allow_note(f"Codex gate: no Codex review for {', '.join(missing)}, but the Codex "
                          f"usage limit was reached; pushes are allowed without a review until "
                          f"{stamp(until)}. Write 'Codex review skipped: usage limit' in the PR body.")
    return deny(f"Codex gate: no Codex review recorded for {', '.join(missing)}. Check out the "
                f"branch and run `{SELF} review --dir {dirs[0]}` (add `--base <branch>` if the PR "
                "base is not the default), fix real findings, commit, review again if the commit "
                "changed, then push. If Codex reports its usage limit, the script records that and "
                f"pushes are allowed for {USAGE_SKIP_HOURS:g} h.")


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
