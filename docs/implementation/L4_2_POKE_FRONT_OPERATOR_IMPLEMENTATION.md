# L4.2 Poke Front Operator Implementation

Date: 2026-06-07

## Problem

The bot was technically online, but it did not behave like a Poke-style personal operator.
The main mismatch was routing: every plain Telegram message without a slash or at-mention became a `codex_default` background task.
That made normal conversation slow, formal, and task-card oriented.

## Change

Plain messages now route to `/chat` with `operators=["host"]`.
`/chat` does not create a task and does not run in the background.

The front operator:
- answers short conversational messages immediately;
- uses Grok API for a concise Poke-like response when available;
- falls back to a local deterministic response if Grok is unavailable or budget-limited;
- keeps heavy work on explicit/escalated routes.

Natural intent routing now recognizes:
- `co możesz?` -> `/capabilities`
- `zrób plan ...` / `przygotuj plan ...` / `wdrażaj ...` -> `/flow`
- `skonsultuj z council ...` -> `/council`
- `zrób research ...` / `zbadaj ...` / `poszukaj ...` -> `@research`

## Updated Contract

Default Telegram behavior:
- ordinary text -> fast `/chat`, no `task_id`;
- `@codex` -> Codex read-only background job;
- `@claude-flow` or `/flow` -> Claude Opus 4.8 background workflow;
- `@research` -> Grok background research;
- `/council` -> structured Council background job;
- local writes/patches/execution still require approval.

## Verification

Local:
- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -X utf8 tests/test_ai_council.py`
- result: 67/67 OK

New acceptance criteria covered by tests:
- plain message routes to `/chat`;
- plain message does not need a task;
- plain message does not background;
- chat fallback is user-facing, not a command dump;
- natural `zrób plan`, `zrób research`, and `co możesz?` route correctly.
