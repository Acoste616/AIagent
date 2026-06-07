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

The complete target is 100% Poke-like behavior or better:

- GPT/Codex and Claude are used through Bartek's subscriptions/OAuth where possible.
- Grok is used through API key for source-backed research, especially X/Twitter research.
- Desktop is the always-on local server and execution surface.
- OpenClaw/Hermes capabilities provide memory, local workspaces, safe execution, verification, and operator communication.
- Telegram/iPhone are the primary private UI until a stable private iMessage/Apple Messages layer exists.

## Implementation Loop

For non-trivial feature work, the system should use this loop:

1. Grok gathers a research pack for Claude from X/Twitter, GitHub, Reddit, official docs/pages, and web sources where available.
2. Claude Opus 4.8 reads Grok's material, the local AI Council code, this Poke target, and OpenClaw/Hermes context, then creates a code/workflow plan.
3. Codex 5.3 Spark or another delegated Codex worker implements the scoped patch to reduce host token burn.
4. Host Codex audits the worker output, runs tests, optionally asks Claude Code for review, deploys to Windows, and performs Telegram smoke checks.

The delegated worker is a cost-control step, not a replacement for Grok research, Claude planning, or host audit.

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
- Codex worker delegation must preserve the loop: Grok research -> Claude plan -> worker implementation -> host audit.
