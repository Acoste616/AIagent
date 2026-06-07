# L4.36 Poke Host Gap

## Decision

L4.36 fixes the most visible UX failure reported by Bartek: Telegram feedback like
"nie odpowiadasz jak Poke" must not route to a long `/goal` capability dump.

The bot now routes Poke/parity/frustration feedback to `/poke-gap`, a short host
answer that states the truth: Poke parity is not complete, why the current system
still feels different, and what the next implementation sprint should address.

## What Changed

- Added `/poke-gap` as a read-only host route.
- Natural Polish feedback such as "nie odpowiada jak Poke", "nie ma takich możliwości",
  or "gdzie ten cel" routes to `/poke-gap`.
- `/poke-gap` creates one idempotent P0 improvement backlog item:
  `Poke Host gap: domyślna odpowiedź Telegrama musi działać jak operator`.
- Health, selftest, capabilities, and system status now report L4.36.
- Regression tests cover the exact frustrated Telegram-style message.

## Why This Matters

Poke-like UX is not only a list of integrations. The first requirement is a
messaging-first host that responds like an operator:

- short diagnosis,
- explicit decision,
- one next move,
- no long internal status dump,
- no false claim that parity is already done.

## Still Missing

This does not complete Poke parity. The next gaps remain:

- action cards for common intents,
- provider dedupe/read-before-write before broader external writes,
- Drive write executor,
- stronger proactive recipes,
- iPhone/iMessage bridge.

## Verification

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m pytest tests/test_ai_council.py::RoutingTests -q`
- `python3 -m pytest -q`
- `python3 ai_council.py respond "Ani nie odpowiada on jak poke nie ma takich możliwości, o co chodzi gdzie ten cel ?"`
