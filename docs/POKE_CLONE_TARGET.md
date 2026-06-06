# Poke-like Clone Target

Date: 2026-06-06

## Evidence From Grok X Research

Poke's strongest public features:

- Apple Messages approval and native messaging UX.
- "No download, no signup" onboarding.
- Recipes as the main no-code integration mechanism.
- Fast in-thread actions after infrastructure upgrade.
- Persistent assistant memory and proactive nudges.
- Cost transparency is a visible user complaint.
- Public technical details about backend/MCP/local bridge are limited.

Source: `docs/research/grok-x-poke-research-2026-06-06.md`.

## Product Goal

Create a private Bartek Agent OS that feels like texting one capable assistant, while internally routing work to Codex, Claude, Grok, memory, recipes, and safe execution.

## Phases

1. Messaging core: Telegram-first, fast ACK, background tasks, status, artifacts.
2. Poke recipes: reusable user-level workflows with triggers and outputs.
3. Council tournament: Claude planner, Grok researcher/red-team, Codex executor, host decision.
4. Safe execution: risk officer, sandbox, approval, verify, rollback.
5. Read-only integrations: memory, GitHub, Gmail, Calendar, Drive.
6. iPhone capture: Shortcuts endpoint, voice/screenshot/share-sheet flows.
7. Apple Messages bridge: private bridge first, public Messages for Business only later.

## Non-Negotiables

- Telegram must never block on long model work.
- Every long task must produce a `task_id`.
- Every meaningful task must produce artifacts.
- Every external write/high-risk action must require approval.
- Costs and model usage must be visible.
- Grok X research must work through the xAI API, not through screenshots or guesses.
- Claude long workflow must get enough time and write a report.

