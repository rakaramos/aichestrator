# aichestrator

Rafael's orchestrator agent. It watches Trello, Slack and GitHub, does the test requests on real phones, looks after open PRs, and replies with evidence. This repo holds its prompt, rules, state and device scripts, so they can be read, tweaked and versioned.

## Layout

| Path | What |
|---|---|
| `prompts/tick.md` | The prompt for each tick |
| `rules/` | Working rules: open requests, Slack status reactions, device automation |
| `config/watch.json` | What to watch: Slack channel IDs, GitHub orgs, the owner |
| `config/devices.local.json` (copy of `config/devices.example.json`, not committed) | Test phones: UDIDs, WebDriverAgent ports, screen sizes |
| `state/open-requests.json` | Ledger of open requests (who asked, what, the next step, blocked on whom) |
| `scripts/ios/` | WebDriverAgent client and helpers (tap and dump, cover-sheet screenshot, chat input) |
| `scripts/android/` | adb helpers (UI dump, app path after a push tap, close like a person) |
| `scripts/web/` | Chrome DevTools Protocol helpers for app web views (evaluate, capture bearer, Firebase token from heap) |
| `docs/poller.md` | Plan for an always-on poller that does not depend on one Claude session |

## Running a tick

In a Claude Code session in this repo, run the prompt in `prompts/tick.md` by hand or on a timer (`/loop 30m`). The rules in `rules/` explain how to handle each item.

## Secrets

Never commit tokens, passwords or test-account credentials. The scripts read them from the environment or the Keychain at run time. The Firebase token helpers write to a mode-600 file outside the repo.

## Changing the orchestrator

Every change to the prompt, the rules or the scripts goes to this repo as a commit, through a pull request.
