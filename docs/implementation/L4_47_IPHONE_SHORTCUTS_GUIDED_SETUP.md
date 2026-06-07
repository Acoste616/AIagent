# L4.47 iPhone Shortcuts Guided Setup

L4.47 adds a guided setup flow for the iPhone Shortcuts layer. L4.45 made the listener operable, and L4.46 surfaced the missing setup in Agent Inbox. L4.47 turns that blocker into a concrete setup path.

## What Changed

- `/shortcuts` now reports `iPhone Shortcuts L4.47`.
- `/shortcuts setup` returns a guided activation checklist.
- `/agent` and proactive `iphone_setup` nudges point to `/shortcuts setup`.
- The setup view reports:
  - token state,
  - endpoint,
  - bind scope,
  - launcher path,
  - blockers,
  - iOS payload examples,
  - next action.

## Safety

- No token is generated automatically.
- No `.env` file is edited automatically.
- No Shortcuts listener is started automatically.
- No external write or publish action is performed.
- Setup only describes the approved path and keeps daemon start behind explicit approval.

## Main Blockers

- `AI_COUNCIL_SHORTCUT_TOKEN` must be configured by the operator.
- `AI_COUNCIL_SHORTCUT_HOST=127.0.0.1` is local-only and not enough for an iPhone unless a local bridge is used.
- Listener start remains manual/approval-gated through `windows-deploy/start-ai-council-shortcuts.ps1`.

## Verification

- `python3 -m pytest tests/test_ai_council.py -q -k 'shortcut or shortcuts or agent or proactive'`
- `python3 -m pytest tests/test_ai_council.py -q`
- `/agent` top item points to `/shortcuts setup` when token is missing.
- `/shortcuts setup` includes blockers and does not reveal or generate a token.
