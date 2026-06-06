# L3.5 Delivery Cards Implementation

Date: 2026-06-07

## What Changed

- Added final task delivery cards for completed background jobs.
- Completed task messages now include inline buttons:
  - `Status`
  - `Details`
  - `Facts`
  - `Next`
- Start/running task messages still keep `Cancel`.
- Added Telegram callback handling for `facts:<task_id>` and `next:<task_id>`.
- Updated system status and capabilities to `L3.5 active`.

## Why

The bot already created task artifacts, but final background results were sent as plain text. That made long-running tasks and media-derived child tasks feel unfinished because Telegram did not expose the artifact workflow directly from the final message.

L3.5 makes the final result act like an operational inbox card: the answer is short, and the next useful views are one tap away.

## Safety

- No new external write actions.
- No shell executor changes.
- No daemon or bridge changes.
- No route semantics changed.
- Existing cancellation remains available only on start/running cards.

## Verification

Local Mac:

- `python3 -X utf8 tests/test_ai_council.py`
- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- Result: `60/60 OK`

Windows Desktop:

- `python -X utf8 tests\test_ai_council.py`
- `python -m py_compile ai_council.py tests\test_ai_council.py`
- `capabilities_response()` returns `L3.5 active`
- `task_delivery_reply_markup()` returns `Status`, `Details`, `Facts`, `Next`
- Scheduled task restarted and running.

## Current Desktop State

- Project: `D:\ai-council`
- Scheduled task: `Bartek AI Council Telegram`
- Process mode: `python -X utf8 -u D:\ai-council\ai_council.py serve --send`
- Health: env OK, Codex OK, Claude OK, Claude Flow Opus 4.8 OK, Grok OK.

