# L4.18 Budget Guard / Kill Switch

Date: 2026-06-07

## Goal

Make autonomous loops and expensive model calls controllable from Telegram before adding more Poke-like automation.

This is not full Poke parity. It is the safety layer that lets future autonomous recipes run without silently burning calls or continuing when Bartek wants the system stopped.

## Implemented

- New durable control state:
  - `state/control.json`
- New command:
  - `/control`
- Natural route:
  - `pokaż kontrolę`
  - `pokaż limity`
  - `kill switch`
- Model guard now applies to all model operators:
  - Codex
  - Claude
  - Claude Flow
  - Grok
  - Grok-backed LLM router
- Scheduler guard:
  - `run_due_recipes()` stops when scheduler is paused or global kill switch is active.
- Proactive guard:
  - `run_proactive_scan()` stops when proactive scan is paused or global kill switch is active.
- `/cost`, `/health`, `/loops`, `/goal`, `/selftest`, and status copy show L4.18 state.

## Control Commands

```text
/control status
/control kill <reason>
/control resume all
/control pause models <reason>
/control pause scheduler <reason>
/control pause proactive <reason>
/control set total-calls <n>
/control set total-budget <usd>
/control set operator <name> calls <n>
/control set operator <name> budget <usd>
/control reset
```

`0` disables a numeric limit.

## Safety

- `control.json` is written atomically via temp file + `os.replace`.
- Invalid `control.json` fails closed for model calls and autonomous automation.
- `/control status` remains available so the failure can be diagnosed.
- Telegram control writes require the allowed chat id when a chat id is present.
- Global kill switch has priority over granular pause flags.
- USD limits are checked pre-call using the same estimated cost used by the cost ledger.

## Known Limits

- The cost ledger is still append-only and not fully serialized across multiple simultaneous OS processes. This is acceptable for the current single-listener baseline, but stronger reservation/locking is the next hardening step before high-concurrency execution.
- USD limits are estimate-based. One in-flight call can still exceed a hard dollar boundary if the provider's real cost differs from the estimate.
- Daily reset is UTC through `today_utc()`.

## Verification

Local:

```text
python3 -m py_compile ai_council.py tests/test_ai_council.py
python3 -m unittest tests/test_ai_council.py
```

Result:

```text
Ran 144 tests
OK
```

Covered by tests:

- `/control` routing;
- natural `pokaż kontrolę` routing;
- scheduler pause does not mark the recipe window as run;
- global kill switch blocks model calls;
- global daily call limit blocks all operators;
- global estimated USD limit blocks the next estimated call;
- per-operator call limit blocks only the matching operator;
- invalid control file fails closed;
- unauthorized Telegram chat cannot write control state;
- proactive scan pause blocks new nudges.
