# L4.46 Mobile Activation Advisor

L4.46 makes Agent Inbox proactively surface the next iPhone/Poke-parity blocker: Shortcuts is implemented, but it cannot be active until `AI_COUNCIL_SHORTCUT_TOKEN` is configured and the listener is explicitly started.

## What Changed

- `/agent` now reports `Agent Inbox L4.46`.
- If `AI_COUNCIL_SHORTCUT_TOKEN` is missing, `/agent` adds a high-priority `iphone_setup` item.
- The item points to `/shortcuts` instead of auto-running anything.
- Proactive scan can create a daily `iphone_setup` nudge when the token is missing.
- `/health` exposes `agent_mobile_advisor=L4.46`.
- `/selftest` starts its version line with `L4.46 Mobile Activation Advisor`.

## Safety

- No token is generated automatically.
- No env file is edited automatically.
- No Shortcuts daemon is started automatically.
- `/agent run` cannot bypass setup approval; it only points to `/shortcuts`.

## Why This Matters

Poke-like UX should not wait for the user to remember setup commands. The system should notice the next blocked capability and put it into the priority inbox.

This layer turns the L4.45 Shortcuts service pack from a hidden readiness state into an operator-visible next action.

## Verification

- `python3 -m pytest tests/test_ai_council.py -q -k 'agent or proactive or shortcut'`
- `python3 -m pytest tests/test_ai_council.py -q`
- `/agent` includes `iphone_setup` when Shortcuts token is missing.
- `/nudges` can show `iphone_setup` after proactive scan.
