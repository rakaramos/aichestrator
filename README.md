# aichestrator

Rafael's orchestrator agent. It watches Trello, Slack and GitHub, does the test requests on real phones, looks after open PRs, and replies with evidence. This repo holds its prompt, rules, state and device scripts, so they can be read, tweaked and versioned.

## Layout

| Path | What |
|---|---|
| `prompts/tick.md` | The prompt for each tick |
| `rules/` | Working rules: open requests, Slack status reactions, Slack message format, device automation |
| `config/watch.json` | What to watch: Slack channel IDs, GitHub orgs, the owner |
| `config/devices.local.json` (copy of `config/devices.example.json`, not committed) | Test phones: UDIDs, WebDriverAgent ports, screen sizes |
| `state/` (not tracked) | Local runtime state: the open-request ledger `state/open-requests.json`, and later the poller's cursor and inbox. Created on first run. |
| `scripts/ios/` | WebDriverAgent client and helpers (tap and dump, cover-sheet screenshot, type and send) |
| `scripts/android/` | adb helpers (UI dump, WebView location after a push tap, close an app like a person) |
| `scripts/web/` | Chrome DevTools Protocol helpers for app web views (evaluate, capture bearer, Firebase token from heap) |
| `docs/poller.md` | Plan for an always-on poller that does not depend on one Claude session |

## Running a tick

In a Claude Code session in this repo, run the prompt in `prompts/tick.md` by hand or on a timer every 10 minutes (`/loop 10m`). The rules in `rules/` explain how to handle each item.

## State is local

The repo holds only code, prompts, rules and config. Runtime state (`state/`) stays on the machine and is git-ignored. If `state/open-requests.json` is missing, the tick starts it as an empty array `[]`.

## Secrets

Never commit tokens, passwords or test-account credentials. The scripts read them from the environment or the Keychain at run time. The Firebase token helpers write to a mode-600 file outside the repo.

## Changing the orchestrator

Every change to the prompt, the rules or the scripts goes to this repo as a commit, through a pull request.
