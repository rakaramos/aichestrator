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

A `PreToolUse` hook on Bash (`codex_gate.py hook`, in `~/.claude/settings.json`) blocks `git push` when `HEAD` has no recorded review. It lets these through:

- A `HEAD` with a recorded review.
- A merge of the base branch that does not change the branch diff (the diff hash is the same as at the last review).
- `--dry-run`, `--delete`, `--tags`, `--help`, and a delete refspec (`:branch`).
- A repo without a remote.

It blocks `git commit … && git push` in one command: commit, review, then push.

## When the Codex usage is gone

When Codex answers that the usage limit is reached, the review script records that in `~/.codex-gate/usage-gone.json`. For the next 3 hours (`CODEX_GATE_USAGE_SKIP_HOURS`) the gate lets pushes through without a review. Then:

- Write "Codex review skipped: usage limit" in the PR body.
- Review the diff yourself before the push.
- After the window, the gate blocks again. Run the review once more: if the usage is still gone, the script opens a new window.

Any other Codex failure (a timeout, a network error, a login error) keeps the push blocked. Fix the cause or tell the owner.
