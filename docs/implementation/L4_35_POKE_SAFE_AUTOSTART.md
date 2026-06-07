# L4.35 Poke Safe Autostart

## Purpose

L4.35 fixes the main UX gap that made Telegram feel unlike Poke: safe work no longer stops at "type `start task-...`".

For R0 read-only/planning work, Action Planner now starts the recommended route immediately and returns the background task card in the same Telegram answer.

## Behavior

Safe auto-start applies only when all conditions are true:

- `AI_COUNCIL_ACTION_PLANNER_AUTOSTART_SAFE` is enabled, default `true`.
- The plan does not require approval.
- Risk is exactly `R0`.
- The command is on the safe allowlist:
  - research routes,
  - x research routes,
  - Claude Flow,
  - Council,
  - recipes,
  - task creation,
  - `/connector` only for read-only subcommands such as `brief`, `sync`, `check`, `search`.

The Telegram result includes:

```text
AUTO-START: tak, bo to bezpieczny tryb R0.
START:
[AI Council] task-...
ETAP: START
Status: /status task-...
Progress: /progress task-...
```

If start fails, the response says:

```text
AUTO-START: próba nieudana.
```

## Reminder And Calendar Intent

Natural reminder/calendar phrasing now routes into Action Planner:

- `hej, czy możesz mi jutro przypomnieć o spotkaniu z Tomkiem?`
- `dodaj do kalendarza ...`
- `ustaw reminder ...`

Those requests create a Calendar integration draft and stay behind approval. They do not create calendar events directly.

## Safety

Still blocked without approval:

- Gmail/calendar/Drive/GitHub external write,
- provider execution,
- shell commands,
- publish/contact/delete/money/DNS/auth/billing.

The broad `/connector` command is not globally auto-startable. Only read-only connector subcommands can auto-start.

## Verification

Mac verification:

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m pytest -q tests/test_ai_council.py`
- Result: `205 passed`.

Claude Code review found two blocking issues:

- Gmail draft risk inconsistency,
- broad calendar noun risk over-match.

Both were fixed before deploy:

- Gmail draft default connector risk is R3, while explicit send/contact wording can still escalate to R4.
- Plain nouns like `spotkanie` and `wydarzenie` no longer inflate `risk_level_for_text()` without action intent.
- Common words like `event` and `reminder` no longer force the Calendar connector without reminder/action intent.
- `/connector` auto-start is scoped to read-only subcommands and handles empty prompts without crashing.

## Not Full Poke Parity

This layer improves the Telegram feel, but parity still needs:

- better front tone/voice,
- Drive provider write adapter,
- provider dedupe/read-before-write,
- stronger proactive topic ownership,
- iPhone Shortcut runtime hardening,
- private iMessage/Apple Messages bridge.
