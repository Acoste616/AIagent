# L4.6 Front Brain v1

Date: 2026-06-07

## Goal

Move AI Council closer to Poke-like behavior by adding:

- conversation thread memory per Telegram chat;
- a safe LLM intent router;
- route-source auditability.

This addresses the main Claude Code audit finding: the system had good command infrastructure, but ordinary language still depended mostly on keyword prefixes and had no local conversation state.

## Conversation State

New state file:

- `D:\ai-council\state\conversations.jsonl`

New functions:

- `append_conversation_turn(chat_id, role, text, route)`
- `recent_conversation(chat_id, limit=6)`

Turns are isolated by `chat_id_hash` and store:

- role: `user` or `assistant`;
- compact text;
- command;
- route source;
- confidence.

## LLM Router

New functions:

- `llm_route(text, chat_id)`
- `route_message(text, chat_id)`

Routing order:

1. explicit `/` or `@` commands;
2. deterministic keyword/natural intents;
3. LLM router for ordinary natural messages;
4. safe `/chat` fallback.

Allowed LLM-router commands:

- `/chat`
- `@research`
- `/xresearch`
- `/flow`
- `/council`
- `/task`
- `/status`
- `/details`
- `/facts`
- `/next`
- `/cost`
- `/errors`
- `/improvements`

Blocked from LLM-router:

- write/append/patch;
- execute/rollback;
- approve/deny;
- publish/contact/delete/DNS/auth/billing style actions.

Low confidence or invalid JSON falls back to `/chat`.

## Runtime Integration

`listen_once()` now uses `route_message()` for Telegram text messages.

Each handled text message now writes:

- one user turn;
- one assistant turn;
- `route_source` and `confidence` to audit.

`/chat` now includes recent conversation turns in the Grok payload, so follow-up prompts like "a teraz krócej" or "z tego zrób plan" have local context.

`/health` now includes:

- `llm_router: on/off`
- recent `route_sources`

## Verification

Local:

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -X utf8 tests/test_ai_council.py`
- result: 82/82 OK

Covered by tests:

- strict JSON LLM route to `@research`;
- unsafe side-effect command rejected by LLM router;
- low confidence route falls back to `/chat`;
- missing `XAI_API_KEY` disables LLM router;
- routing priority: explicit -> keyword -> LLM;
- conversation history is isolated by `chat_id`;
- `/chat` sends recent conversation context to Grok;
- `listen_once()` persists user and assistant turns;
- audit rows include `route_source` and `confidence`.
