# L4.26 Agent Inbox

Date: 2026-06-07

## Problem

The system had many pieces of a Poke-like agent: tasks, progress, follow-ups, nudges, improvements, errors, recipes, and approvals. They were still exposed as separate command surfaces. Bartek had to manually inspect each list and decide what to do next.

## Implemented

- Added `/agent` and `/inbox` as one front operator command center.
- Added natural routing for `co dalej`, `co teraz`, `agent inbox`, and `czym się zająć`.
- `/agent` aggregates:
  - running and stuck tasks,
  - pending approvals,
  - follow-up proposals,
  - open improvements,
  - recent errors,
  - proactive nudges.
- `/agent` returns one priority decision, facts, ranked items, exact `NEXT`, and an optional safe `RUN`.
- Added `/agent run [id]` for safe local next steps:
  - safe follow-up proposal through the existing approval runner,
  - `/improve apply <id>` planning in the background,
  - safe recipe runs such as `error_audit_twice_daily` or `feature_evolution_loop`.
- R3/R4 and external write/contact/publish/delete/auth/billing/DNS still require explicit approval and are not bypassed by `/agent run`.
- Proactive scan now creates a nudge for the top open improvement, so autonomous loops can surface the next implementation candidate without Bartek manually opening `/improvements`.

## Verification

- Mac tests: `167/167 OK`.
- Syntax check: `python3 -m py_compile ai_council.py`.

## Remaining Gap

This is the first command-center layer. Full Poke parity still needs iPhone capture as a primary inbox, deeper write-capable connectors after approval, private iMessage bridge, and stronger integration-backed autonomy.
