# L4.1 Telegram Selftest Implementation

Date: 2026-06-07

## What Changed

- Added `/selftest` command.
- Added natural intent routing for:
  - `selftest`
  - `test systemu`
  - `sprawdź wszystko`
- Selftest reports:
  - project path,
  - env presence,
  - Telegram configuration,
  - operator binary status,
  - running/stuck task counts,
  - artifact/workspace directories,
  - Poke/Grok/Claude research docs,
  - Shortcuts token state.

## Why

The system already had `/health`, but goal-level verification needed a single Telegram-visible command that proves the bot can answer from the live channel and shows whether the research, operator, artifact, and safety layers are present.

When Bartek sends `/selftest` in Telegram and receives the response, that single flow proves live Telegram inbound and outbound for the running desktop service.

## Safety

- No model calls.
- No external writes.
- No shell execution.
- No new listener.
- No secrets exposed; only configured/missing state is reported.

## Verification

Local Mac:

- `python3 -X utf8 tests/test_ai_council.py`
- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- Result: `66/66 OK`

Windows Desktop:

- `python -X utf8 tests\test_ai_council.py`
- `python -m py_compile ai_council.py tests\test_ai_council.py`
- Result: `66/66 OK`
- `selftest_response()` shows Grok X research, Claude plan, Claude tournament and target docs as `OK`.
- Real Telegram `sendMessage` with selftest output returned `telegram_send=True`.

Covered tests:

- `/selftest` route.
- Natural intent route.
- Selftest response builds without model/network calls.
