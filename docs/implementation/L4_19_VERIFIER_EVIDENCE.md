# L4.19 Verifier Evidence

Date: 2026-06-07

## Goal

Make local execution more operator-like by turning `/verify` into durable evidence, not just a chat response.

This does not yet make AI Council a full shell executor. It strengthens the existing workspace write/append/patch execution path so the system can prove whether a local action actually meets its expected result.

## Implemented

- `/verify <action_id>` now appends a verification event to `state/actions.jsonl`.
- Successful verification changes workspace action status to:
  - `verified`
- Failed verification changes workspace action status to:
  - `verify_failed`
- Verification stores:
  - `verified_at`
  - `verification_status`
  - `verification_result`
  - `verification_checks`
- `/rollback <action_id>` now works after:
  - `executed`
  - `verified`
  - `verify_failed`
- Verifying a rolled-back action keeps status `rolled_back` and records rollback verification evidence.
- Verifying a non-executed action does not mutate the action ledger and does not unlock rollback.

## Acceptance Checks

The verifier checks current local state against action payload:

- workspace path resolves inside `D:\ai-council\workspaces`;
- action is in an executable/verifiable state;
- target exists when expected;
- write content equals expected payload;
- append content equals before snapshot + appended text;
- patch content equals expected one-replacement result;
- rollback restores the before snapshot or removes a file that did not exist before.

## Why It Matters

Before L4.19, `/verify` could say `OK`, but the durable action ledger still only showed `executed`. That made later agents unable to distinguish "ran" from "proved".

After L4.19, the ledger records whether execution was verified or failed verification.

Claude Code review found one pre-deploy bug: `/verify` on a pending action could have written `verify_failed`, which would unlock `/rollback` even though the action never executed. The implementation now leaves pending actions unchanged and the regression is covered by tests.

## Verification

Local:

```text
python3 -m py_compile ai_council.py tests/test_ai_council.py
python3 -m unittest tests/test_ai_council.py
```

Result:

```text
Ran 146 tests
OK
```

Covered by tests:

- workspace write execute -> verify persists `verified`;
- verification output includes concrete checks;
- rollback works after `verified`;
- verifying rollback records evidence while preserving `rolled_back`;
- tampered file produces `verify_failed`, not `OK`;
- rollback still works after `verify_failed`.
- pending action `/verify` does not become `verify_failed` and cannot be rolled back.
