# AI Council L3.4 Media Intent Routing Implementation

Date: 2026-06-07
Target runtime: `D:\ai-council` on Windows Desktop

## Outcome

L3.4 makes captured media behave like normal Telegram text. After text
extraction, Grok vision/OCR, or xAI STT, AI Council derives an intent and sends
it through the same `route_text` path used for regular messages.

This is the Poke-like step where a voice note can become real work:

```text
voice note -> STT transcript -> route_text -> /flow/background task
```

## Implemented

- `media_intent_text`
- `run_media_derived_route`
- Derived task source:
  - `telegram_media_intent`
- Idempotency key:
  - `media-derived:<parent_task_id>:<hash>`
- Media metadata now includes:
  - `derived_intent`
- Capture summaries include the child task response when available.
- L3.4 capabilities/status labels.
- Config:
  - `AI_COUNCIL_MEDIA_AUTO_ROUTE=true`
  - `AI_COUNCIL_MEDIA_INTENT_MAX_CHARS=3000`

## Safety

Media intent does not get special privileges. It uses the same routing and
guards as normal text:

- model/long tasks go through background jobs,
- local workspace writes become pending actions,
- R3/R4 remains blocked by Risk Officer,
- no shell execution is introduced.

## Verification

Local repository:

```text
Ran 58 tests
OK
```

Windows Desktop:

```text
Ran 58 tests
OK
```

Windows smoke check:

```text
Capabilities L3.4 active
running_background
/flow
```

Windows status after deployment:

```text
Bartek AI Council Telegram: Running
running_tasks: 0
stuck_tasks: 0
codex: OK
claude: OK
claude_flow: OK model=claude-opus-4-8 mode=plan
grok: OK
```

## Boundaries

This layer does not add iMessage, Apple Messages, iOS Shortcuts, shell
execution, external writes, publishing, contact actions, money movement, or
DNS/auth/billing changes.
