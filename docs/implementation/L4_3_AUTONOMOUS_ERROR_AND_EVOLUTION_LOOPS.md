# L4.3 Autonomous Error And Evolution Loops

Date: 2026-06-07

## Goal

Move AI Council toward the long-running Poke-like/OpenClaw-like goal by adding a self-improvement substrate:

- capture runtime and Telegram errors in a dedicated error store;
- expose recent errors through Telegram;
- run a twice-daily error audit loop;
- run a recurring feature evolution loop that chains Grok/X research into Claude Flow planning.

This does not complete Poke parity. It creates the feedback loop needed to keep building and fixing feature by feature.

## Error Store

New paths:

- `D:\ai-council\errors\<YYYY-MM-DD>.jsonl`
- `D:\ai-council\state\errors.jsonl`

Each record contains:

- `error_id`
- `created_at`
- `day`
- `context`
- `severity`
- `message`
- `exception_type`
- sanitized `traceback`
- sanitized event context

Telegram/runtime failures now record errors for:

- Telegram `getUpdates` failures;
- Telegram `sendMessage` failures;
- callback handler exceptions;
- media capture exceptions;
- message handler exceptions;
- failed final response sends.

## Telegram Visibility

New command:

- `/errors`

Natural route:

- `pokaż błędy`
- `sprawdź błędy`
- `errors`

`/health` now includes `errors_24h`.

## Autonomous Recipes

New default recipe: `error_audit_twice_daily`

- enabled by default;
- cron: `0 9,21 * * *`;
- step 1: `/errors recent 20`;
- step 2: Claude Flow audits the error context and proposes concrete patches/tests.

New default recipe: `feature_evolution_loop`

- enabled by default;
- cron: `15 10 * * *`;
- step 1: Grok/X researches latest Poke, messaging agents, recipes, proactive alerts, iPhone/Apple Messages, Hermes/OpenClaw-style execution;
- step 2: Claude Flow turns that research into the next implementation plan against `D:\ai-council`.

Recipe runner now supports `{previous}`, so one step can pass its output to the next step. This is the first concrete implementation of the requested flow:

```text
Grok research -> Claude plan -> Codex audits and implements
```

## Verification

Local:

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -X utf8 tests/test_ai_council.py`
- result: 70/70 OK

Covered by tests:

- `/errors` routes to host;
- natural `pokaż błędy` routes to `/errors`;
- `record_error()` writes both state and daily error JSONL files;
- `/errors` includes recent error IDs and contexts;
- default autonomous loop recipes exist and are enabled;
- `error_audit_twice_daily` runs at `0 9,21 * * *`;
- `feature_evolution_loop` runs at `15 10 * * *`;
- recipes can inject `{previous}` output into later steps.
