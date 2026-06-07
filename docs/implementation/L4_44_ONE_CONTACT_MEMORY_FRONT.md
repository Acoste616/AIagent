# L4.44 One Contact Memory Front

L4.44 improves the default Telegram experience so Bartek AI Council behaves more like one persistent contact instead of a command router.

## What Changed

- `POKE_FRONT_VERSION` is now `L4.44`.
- Local `/chat` fallback reads the latest conversation turn for the same Telegram chat.
- Follow-up prompts such as `a teraz krócej`, `rozwiń`, or `doprecyzuj` refer to the previous local thread when Grok chat is unavailable or gated.
- `co dalej` uses the recent thread context and names one next strategic move.
- Grok front-chat system prompt now explicitly treats Telegram as one continuous contact and uses previous thread messages.
- `/health`, `/selftest`, `/goal`, `/capabilities`, and Poke Gap expose `L4.44 One Contact Memory Front`.

## Why

Poke-like UX depends on conversational continuity. A user should not have to restate context after every short follow-up. Before L4.44, recent conversation turns were stored and passed to the LLM, but deterministic local fallback still sounded like a fresh empty chat when the front LLM was gated or unavailable.

## Safety

- No new daemon or bridge is started.
- No external writes are added.
- Conversation context is scoped by Telegram `chat_id` hash.
- Mutating actions still go through existing approval paths.

## Verification

- Tests cover:
  - latest conversation hint is isolated by chat;
  - local follow-up fallback uses the previous thread;
  - `co dalej` includes recent context and the next Poke-parity move;
  - Grok front-chat prompt carries the continuous-contact rule.
