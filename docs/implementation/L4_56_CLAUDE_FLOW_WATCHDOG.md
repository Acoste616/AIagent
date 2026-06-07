# L4.56 Claude Flow Watchdog

## Purpose

Claude Flow is required in the target Grok -> Claude -> Codex loop, but long-running or stuck Claude calls can otherwise disappear as a generic `unavailable` string. The autonomous error loop needs those failures in the same error stream it audits twice daily.

## Changes

- Added `CLAUDE_FLOW_WATCHDOG_VERSION = "L4.56"`.
- `call_subprocess_operator()` now records subprocess failures in `errors.jsonl`:
  - timeout
  - missing command
  - non-zero exit
- Error context is operator-specific, for example `operator_claude-flow`.
- Loop synthesis skips failed planning step bodies such as `[Claude Flow] unavailable: timeout...` and falls back to the latest successful step, usually Grok triage.
- `/health`, `/status`, `/selftest`, and `/capabilities` expose the watchdog version.

## Verification

- Regression test proves a Claude Flow timeout is recorded as an operator error with the task id.
- Regression test proves an error-audit recipe can still create an actionable improvement from Grok triage when Claude Flow times out.

