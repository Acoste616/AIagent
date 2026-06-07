# L4.27 iPhone Primary Capture

Date: 2026-06-07

## Problem

The Telegram core had an optional Shortcuts endpoint, but iPhone input was not treated as a first-class part of the Poke-like workflow. Share Sheet links, voice notes, screenshots, and control actions needed to land in the same task/artifact/inbox system as Telegram work.

## Implemented

- Added `/shortcuts` as a read-only command that reports endpoint status, token configuration, payload shapes, safety rules, and recent iPhone Shortcut tasks.
- Added natural routing for phrases such as `iphone shortcuts`, `pokaż skróty`, and `iphone inbox`.
- Added iPhone Shortcut action routing:
  - `{"action":"agent"}` opens `/agent`,
  - `{"action":"status","task_id":"task-..."}` opens `/status`,
  - `progress/details/facts/next/health/selftest/goal/shortcuts` route through the existing command handlers,
  - `approve/deny/cancel` return a blocked response and point back to Telegram approval.
- Share Sheet URL payloads now default to `/recipe run research_brief ...`, so links become background research tasks instead of ordinary chat.
- Plain text Shortcut asks are persisted as completed `iphone_shortcut_text` tasks with artifacts, so they appear in `/agent`.
- Text Shortcut idempotency now suppresses duplicate iOS retries within the normal idempotency window.
- Task IDs now include a unique seed so two similar Shortcut/operator inputs in the same second cannot collide in state or artifacts.
- Media/voice/screenshot/file Shortcut payloads continue through capture, analysis, media-to-intent routing, and artifact creation.
- `/agent` now includes recent iPhone Shortcut inputs as `iphone_capture` inbox items and reports `iphone_inputs`.

## Safety

- The Shortcut endpoint remains token-gated.
- `/shortcuts` does not print the token value.
- Shortcuts can capture/read/research and inspect existing tasks.
- Mutating Shortcut actions such as `approve`, `deny`, and `cancel` are blocked by default and must go through Telegram approval.
- No new daemon or external write path is started by this implementation.

## Verification

- Mac tests: `174/174 OK`.
- Syntax check: `python3 -m py_compile ai_council.py tests/test_ai_council.py`.
- Windows Desktop tests: `174 passed, 104 subtests passed`.
- Windows Desktop syntax check: `python -m py_compile ai_council.py tests\test_ai_council.py`.
- Windows Desktop smoke: `dry-route /shortcuts`, natural `pokaż skróty`, and `doctor` all OK after listener restart.

## Remaining Gap

This makes iPhone capture first-class in the core. It still needs device-side Shortcut setup, optional runtime hardening for the local endpoint, deeper integration-backed autonomy, and later private Apple Messages/iMessage bridging after the Telegram core is stable.
