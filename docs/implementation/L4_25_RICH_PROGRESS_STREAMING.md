# L4.25 Rich Progress Streaming

Date: 2026-06-07

## Problem

Long background tasks could look silent from Telegram. The bot sent `START`, sometimes `RUNNING`, then a final delivery card. For Poke-like use, Bartek needs visible proof that the agent is still working and a quick way to inspect where a task is stuck.

## Implemented

- Added durable progress events in `state/progress_events.jsonl`.
- Added progress stages: `START`, `PREPARING`, `RUNNING`, `COLLECTING`, `DELIVERING`, `COMPLETED`, `FAILED`, `CANCELLED`.
- Added approximate percent markers for each stage.
- Added `/progress <task_id>`.
- Added natural routes for `progress task-...` and `postęp task-...`.
- Added progress timeline to `/status <task_id>`.
- Background workers append events for every stage, send `RUNNING`/final delivery for short jobs, and use heartbeat plus gated intermediate updates for longer jobs.
- Updated `/goal`, `/capabilities`, `/health`, `/selftest`, and command lists to expose L4.25.

## Boundaries

This is stage-level progress and heartbeat, not token-level model streaming. The goal is to remove perceived silence and make failed/stuck work inspectable without spamming Telegram on short jobs. Full Poke parity still requires stronger proactive agent loops, iPhone capture, private iMessage bridge, optional token-level streaming, and deeper write-capable integrations after approval.

## Verification

- Mac tests: `163/163 OK`.
- Syntax check: `python3 -m py_compile ai_council.py`.
