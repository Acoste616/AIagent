# L4.42 Default Front Host

L4.42 improves the Telegram front-host behavior so AI Council answers more like a personal operator and less like a technical status page.

## Changes

- Poke/parity frustration now returns `Poke Gap L4.42`.
- The Poke Gap response no longer points back to `/goal` or stale Drive/read-before-write gaps.
- It reports that L4.41 read-before-write is already deployed, then names the current real gap: front UX and proactive ownership.
- The default chat fallback now gives one operator next move instead of asking the user to learn commands.
- Short ordinary questions can route to the front LLM when Grok chat is configured, while status/system phrases stay local and cheap.
- `/health`, `/selftest`, `/goal`, and `/capabilities` expose L4.42 as the current front layer.

## Safety

- Mutating actions are still behind approval.
- Status, health, selftest, cost, control, and Poke parity markers remain local and do not spend model calls.
- If the front LLM is unavailable or gated, fallback remains deterministic and short.

## Verification

```bash
python3 -m py_compile ai_council.py tests/test_ai_council.py
python3 -m pytest tests/test_ai_council.py -q -k "poke_gap or poke_chat or chat_response or natural_intents_route or short_operator_question or default_chat_fallback"
python3 -m pytest tests/test_ai_council.py -q
```
