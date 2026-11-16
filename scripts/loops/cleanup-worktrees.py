#!/usr/bin/env python3
"""Reclaim disk space from the worktrees of finished request loops.

Usage:
  cleanup-worktrees.py [--apply] [--allow-local-head] [--include-plain] PATH...            # worktree folders under the root
  cleanup-worktrees.py [--apply] ... --from-progress PROGRESS.md... [--protect PROGRESS.md...]
      --from-progress: every root path a closed loop's notes name, plus the notes' own folder
      --protect: never touch a path that an open loop's notes name

Without --apply it only prints what it would do (dry run).

A folder is removed only when all of these hold:
  - it lies directly under the worktrees root (never the root itself or anything outside it);
  - it is a git worktree (a plain folder is reported and kept);
  - it has no uncommitted change to a tracked file;
  - its HEAD commit exists on a remote branch (nothing local only is lost).
    --allow-local-head drops this check and reports how many local-only commits go
    (use it only for a closed request whose result is merged or posted).
--include-plain also removes a plain folder (evidence, copies) when every git worktree
nested in it (two levels deep) passes the same checks; its top-level *.md files are archived.
Before removal, its PROGRESS.md is copied to state/archive/. Files next to the folder named
"<folder>-*.md" are archived too, "<folder>-*.log" files are deleted. Xcode DerivedData folders
whose workspace lies inside the removed folder are deleted as well.
"""
import os, re, shutil, subprocess, sys, plistlib, glob

ROOT = os.environ.get("LOOP_WORKTREES_ROOT", "/Volumes/HD/Developer/worktrees")
ARCHIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "state", "archive")
DERIVED = os.path.expanduser("~/Library/Developer/Xcode/DerivedData")


def git(path, *args):
    r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def size(path):
    r = subprocess.run(["du", "-sk", path], capture_output=True, text=True)
    try:
        return int(r.stdout.split()[0]) * 1024
    except (IndexError, ValueError):
        return 0


def human(n):
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.0f}P"


def derived_for(path):
    found = []
    for info in glob.glob(os.path.join(DERIVED, "*", "info.plist")):
        try:
            with open(info, "rb") as f:
                ws = plistlib.load(f).get("WorkspacePath", "")
        except Exception:
            continue
        if ws == path or ws.startswith(path + os.sep):
            found.append(os.path.dirname(info))
    return found


def nested_repos(real):
    found = []
    for depth1 in sorted(os.listdir(real)):
        p1 = os.path.join(real, depth1)
        if os.path.isdir(p1) and not os.path.islink(p1):
            if os.path.exists(os.path.join(p1, ".git")):
                found.append(p1)
                continue
            for depth2 in sorted(os.listdir(p1)):
                p2 = os.path.join(p1, depth2)
                if os.path.isdir(p2) and not os.path.islink(p2) and os.path.exists(os.path.join(p2, ".git")):
                    found.append(p2)
    return found


def check(path, allow_local=False, include_plain=False, top=True):
    """Return (ok, reason)."""
    real = os.path.realpath(path)
    if top and os.path.dirname(real) != os.path.realpath(ROOT):
        return False, "not directly under the worktrees root"
    if not os.path.isdir(real):
        return False, "missing"
    if not os.path.exists(os.path.join(real, ".git")):
        if not include_plain:
            return False, "plain folder, not a git worktree"
        reasons = []
        for repo in nested_repos(real):
            ok, why = check(repo, allow_local, False, top=False)
            if not ok:
                return False, f"nested {os.path.relpath(repo, real)}: {why}"
            reasons.append(f"{os.path.relpath(repo, real)} {why}")
        return True, "plain folder" + (" with " + "; ".join(reasons) if reasons else "")
    code, out = git(real, "status", "--porcelain", "--untracked-files=no", "--ignore-submodules=all")
    if code != 0:
        return False, "git status failed"
    if out:
        return False, f"uncommitted changes ({len(out.splitlines())} files)"
    code, head = git(real, "rev-parse", "HEAD")
    if code != 0:
        return False, "no HEAD"
    git(real, "fetch", "--quiet", "origin")
    code, remotes = git(real, "branch", "-r", "--contains", head)
    if code != 0 or not remotes:
        if not allow_local:
            return False, f"HEAD {head[:7]} is on no remote branch"
        _, local = git(real, "rev-list", "--count", "HEAD", "--not", "--remotes")
        return True, f"clean, HEAD {head[:7]} local only ({local} local commits dropped)"
    return True, f"clean, HEAD {head[:7]} on {remotes.splitlines()[0].strip()}"


def remove(path):
    real = os.path.realpath(path)
    name = os.path.basename(real)
    os.makedirs(ARCHIVE, exist_ok=True)
    if not os.path.exists(os.path.join(real, ".git")):
        for repo in nested_repos(real):
            _, common = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
            for d in derived_for(repo):
                shutil.rmtree(d, ignore_errors=True)
            if os.path.isfile(os.path.join(repo, ".git")):
                subprocess.run(["git", "-C", os.path.dirname(common), "worktree", "remove", "--force", repo], capture_output=True)
        for f in glob.glob(os.path.join(real, "*.md")):
            shutil.copy2(f, os.path.join(ARCHIVE, f"{name}-{os.path.basename(f)}"))
        for d in derived_for(real):
            shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(real, ignore_errors=True)
        return
    progress = os.path.join(real, "PROGRESS.md")
    if os.path.isfile(progress):
        shutil.copy2(progress, os.path.join(ARCHIVE, f"{name}-PROGRESS.md"))
    code, common = git(real, "rev-parse", "--path-format=absolute", "--git-common-dir")
    main_repo = os.path.dirname(common) if code == 0 else real
    for d in derived_for(real):
        shutil.rmtree(d, ignore_errors=True)
    r = subprocess.run(["git", "-C", main_repo, "worktree", "remove", "--force", real], capture_output=True, text=True)
    if r.returncode != 0:
        shutil.rmtree(real, ignore_errors=True)
        git(main_repo, "worktree", "prune")
    for f in glob.glob(os.path.join(os.path.dirname(real), f"{name}-*")):
        if os.path.isfile(f):
            if f.endswith(".md"):
                shutil.move(f, os.path.join(ARCHIVE, os.path.basename(f)))
            elif f.endswith(".log"):
                os.remove(f)


def paths_from_progress(files):
    pat = re.compile(re.escape(ROOT.rstrip("/")) + r"/([A-Za-z0-9._-]+)")
    out = []
    for f in files:
        with open(f, errors="replace") as fh:
            for m in pat.finditer(fh.read()):
                p = os.path.join(ROOT, m.group(1))
                if os.path.isdir(p) and p not in out:
                    out.append(p)
        d = os.path.dirname(os.path.abspath(f))
        if os.path.dirname(d) == os.path.realpath(ROOT) and d not in out:
            out.append(d)
    return out


def main(argv):
    apply = allow_local = include_plain = False
    progress, protect, paths = [], [], []
    mode = None
    for a in argv:
        if a == "--apply":
            apply = True
        elif a == "--allow-local-head":
            allow_local = True
        elif a == "--include-plain":
            include_plain = True
        elif a in ("--from-progress", "--protect"):
            mode = a
        elif mode == "--from-progress":
            progress.append(a)
        elif mode == "--protect":
            protect.append(a)
        else:
            paths.append(os.path.abspath(a))
    paths += [p for p in paths_from_progress(progress) if p not in paths]
    kept = set(os.path.realpath(p) for p in paths_from_progress(protect))
    if not paths:
        print(__doc__)
        return 2
    total = 0
    for p in paths:
        n = size(p) + sum(size(d) for d in derived_for(os.path.realpath(p))) if os.path.isdir(p) else 0
        if os.path.realpath(p) in kept:
            print(f"KEEP\t{human(n)}\t{p}\tnamed by an open request's notes")
            continue
        ok, reason = check(p, allow_local, include_plain)
        if ok:
            total += n
            if apply:
                remove(p)
            print(f"{'REMOVED' if apply else 'WOULD REMOVE'}\t{human(n)}\t{p}\t{reason}")
        else:
            print(f"KEEP\t{human(n)}\t{p}\t{reason}")
    print(f"{'Reclaimed' if apply else 'Would reclaim'}: {human(total)}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
