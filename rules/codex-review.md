# Codex review before every push

Every push of code changes gets a Codex review of the final branch diff first. This applies to every session: the orchestrator, request loops, review loops and owner sessions.

**Why:** on 2026-11-27 a check of three days of transcripts found that most sessions that pushed code ran no Codex review. Seven sessions pushed between 5 and 77 times with no Codex run. Two PRs were merged without one (exercise#411, photor#222). The only written rule was one line in `prompts/tick.md` about fixes for review comments, and many briefs did not name it. A CodeFox review on GitHub comes after the push and does not replace this review.

## How

1. Commit the change. The review covers committed `HEAD` only.
2. Run the review in the repo or worktree:

   ```bash
   /Volumes/HD/Developer/aichestrator/scripts/codex/codex_gate.py review --dir <repo-or-worktree> [--base <pr-base-branch>]
   ```

   Without `--base`, the script uses the PR base (`gh pr view`), else `origin/HEAD`. It runs `codex review --base origin/<base>` and records the result for `HEAD` in `<git common dir>/codex-reviews/`.
3. Fix the real findings. A new commit is a new `HEAD` and needs a new review.
4. Push in a separate command. Write the result in the PR body (for example "Codex review: no findings", or the findings that you fixed).

## The gate

A `PreToolUse` hook on Bash (`codex_gate.py hook`) checks every `git push` in a command. For each ref the push uploads (the current branch when no refspec is given), it needs a recorded review. It lets these through:

- A commit with a recorded review.
- A merge of the base branch that does not change the branch diff (the diff hash is the same as at the last review of that branch).
- `--dry-run`, `--help`, pushes of tags only (annotated or lightweight), and pushes that only delete refs (`--delete`, or only `:branch` refspecs). A push that also updates a branch (`--tags origin feature`, `:old new`) is checked.

It blocks:

- A push whose folder the hook cannot resolve or read as a git repo (it fails closed): a shell variable in the `cd` or `-C` path, a missing folder, or a folder that is not a repo. Use a literal absolute path.
- `git commit … && git push` in one command: commit, review, then push.
- Pushes of many branches at once (`--all`, `--mirror`, a wildcard refspec, or `push.default=matching`): push each branch by name.

### Limits

The hook reads the shell text of the command. It catches a forgotten review in the usual forms (`git push`, `cd … && git push`, `git -C … push`, several pushes in one command, explicit refspecs). It ignores heredoc bodies and quoted strings that mention a push (commit messages, PR bodies, `echo` text), so a push inside `bash -c "…"` or `eval "…"` is not seen either. It is not a security boundary: a command built to hide a push (for example a push inside `eval`, a script file or an alias) can pass it. Do not write commands like that; push with a plain `git push`.

A detached `HEAD` is checked by commit only: the merge-of-base exemption needs a branch name.

A review counts for its commit whatever base it used. The script takes the PR's own base by default; when you pass `--base`, pass the PR base.

### Install

The hook lives in `~/.claude/settings.json`, next to the other `PreToolUse` Bash hooks:

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "/Volumes/HD/Developer/aichestrator/scripts/codex/codex_gate.py hook",
      "timeout": 60
    }
  ]
}
```

It points at this checkout on `main`, so keep the checkout on `main` (`prompts/tick.md`). The hook allows the push when the script itself fails, so a broken script never blocks unrelated commands; check that it still blocks after each change (pipe a `git push` command into `codex_gate.py hook` in an unreviewed repo).

## When the Codex usage is gone

When Codex answers that the account's usage limit or quota is used up ("usage limit", "insufficient_quota", "exceeded your quota"), the review script records that in `~/.codex-gate/usage-gone.json`. For the next 3 hours (`CODEX_GATE_USAGE_SKIP_HOURS`) the gate lets pushes through without a review. Then:

- Write "Codex review skipped: usage limit" in the PR body.
- Review the diff yourself before the push.
- After the window, the gate blocks again. Run the review once more: if the usage is still gone, the script opens a new window.

Any other Codex failure (a timeout, a network error, a login error) keeps the push blocked. Fix the cause or tell the owner.
