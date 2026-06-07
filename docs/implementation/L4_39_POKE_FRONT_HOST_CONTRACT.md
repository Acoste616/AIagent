# L4.39 Poke Front Host Contract

## Decision

L4.39 makes the default Telegram front less like a technical status page and
more like a Poke-style operator. Feedback such as "not Poke", "where is the
goal", or "no capabilities" must return a short diagnosis, concrete facts, and
one next move.

## What Changed

- `/poke-gap` now uses a shorter L4.39 response:
  - decision,
  - what is wrong,
  - what is changing now,
  - missing Poke-parity capabilities,
  - facts,
  - one next step.
- The first frustration response no longer points Bartek to `/goal`.
- Generic `/chat` fallback now avoids command dumps and asks for one clear
  intent when no task is detected.
- If a missed `/chat` fallback still sees Poke/frustration wording, it delegates
  to a pure Poke-gap message without writing the improvement backlog.
- The fallback uses a narrow frustration/parity match. A routine word containing
  `poke`, such as `pokemon`, does not trigger Poke-gap.
- The pure fallback still reads current task/error counts, so it does not show
  misleading `0/0` facts during incidents.

## Safety

- No new external write capability is added.
- No shell execution is added.
- `/chat` fallback does not write `improvements.jsonl`.
- Existing Action Planner, provider gates, approval, and confirm-token rules
  remain unchanged.

## Verification

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m pytest tests/test_ai_council.py -q -k "poke_gap or chat_response_has_poke_style_fallback or short_greeting"`
- Full local test suite: `216 passed`
