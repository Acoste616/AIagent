# L4.37 Poke Action Cards

## Decision

L4.37 adds Poke-like in-thread actions to the `/poke-gap` response. The previous
L4.36 layer made the response honest and short; L4.37 makes it actionable inside
Telegram without requiring Bartek to type another command.

## What Changed

- `/poke-gap` responses now get Telegram inline buttons:
  - `Agent`
  - `Improve`
  - `Poke research`
  - `Health`
- Added `host:*` callback routing for safe host actions.
- `host:agent` opens `/agent`.
- `host:improve-next` opens `/improve next`.
- If the improvement backlog is empty, `host:improve-next` falls back to Action
  Planner for one next safe Poke-like sprint.
- `host:poke-research` uses Action Planner so safe research can become a task
  and run in the background instead of blocking Telegram.
- `host:health` opens `/health`.
- Button attachment uses a stable `Poke Gap L4.` marker instead of a specific
  version string, so later L4 bumps do not silently drop the action card.

## Why This Matters

Poke's strongest UX pattern is not only answering in a messenger. It also gives
next actions in the same thread. This layer moves Bartek AI Council from
"diagnose the gap" to "diagnose and offer the next operational move".

## Safety

- No external write is added.
- No shell execution is added.
- Research still goes through Action Planner and existing R0/background rules.
- Existing approval gates for R3/R4 actions remain unchanged.

## Verification

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m pytest tests/test_ai_council.py -q -k "poke_gap or host_callback or callback or reply_markup"`
- Full test suite before deployment: `211 passed`.
