# L4.31 Provider Write Gate

Date: 2026-06-07

## Purpose

L4.31 adds a separate approval object for provider writes. It moves the flow beyond manifests without silently writing to Gmail, Calendar, Drive, or GitHub.

The result is an auditable write-request gate:

1. verified integration draft,
2. verified provider manifest,
3. pending provider write request,
4. explicit approval,
5. explicit confirm token,
6. dry-run/blocker artifact,
7. verifier for the dry-run.

## User Flow

1. Build the draft and local pack:
   `/connector draft gmail|calendar|drive|github <intent>`
   `/approve <integration_action_id>`
   `/execute <integration_action_id>`
   `/verify <integration_action_id>`
2. Build and verify the provider manifest:
   `/provider plan <integration_action_id>`
   `/provider verify <integration_action_id>`
3. Create the provider write request:
   `/provider request <integration_action_id>`
4. Approve it:
   `/approve <provider_write_request_id>`
5. Attempt execution with the confirm token:
   `/provider execute <provider_write_request_id> <confirm_token>`
6. Verify the dry-run:
   `/provider verify <provider_write_request_id>`

Readiness required before `/provider request` succeeds:

- provider manifest exists,
- provider manifest has been verified,
- draft has no unresolved `missing_fields`,
- connector auth is configured,
- provider operation is known.

The confirm token is stored in the request payload and shown to Bartek as a local intent-confirmation string. It prevents accidental execution, not malicious use by someone who can read the action log. Real provider execution in L4.32 should use a fresh stored token plus the same explicit approval path.

## Safety Contract

L4.31 still performs no external write:

- no email is sent,
- no Gmail draft is created,
- no calendar event is created,
- no Drive file is created,
- no GitHub issue is opened,
- no provider state is changed.

`/provider execute` writes a local dry-run artifact only:

- `artifacts/provider-write-requests/<request_id>/provider_write_dry_run.json`
- `artifacts/provider-write-requests/<request_id>/provider_write_dry_run.md`

The dry-run records:

- provider operation,
- request body,
- source action,
- intended external write,
- `external_write_performed: false`,
- blocker reason.

## Why This Matters

Poke-like agents feel useful because they can move from conversation to an action pipeline. L4.30 produced the provider manifest but still stopped before a write object existed. L4.31 creates the missing pending write object while keeping write execution blocked.

This is the right shape before real provider adapters: every future write must already have an action id, approval event, confirm token, dry-run artifact, and verifier evidence.

## Remaining Gap

L4.31 is not full provider execution. The next layer is L4.32 Provider Executor v0:

- choose one connector first,
- implement real provider call behind env gate and confirm token,
- verify provider result from source,
- store provider object id/link,
- define undo/rollback policy before enabling writes broadly.

## Verification

- Mac local tests: `185 passed` + `py_compile` + `git diff --check`.
- Claude review: complete; readiness rejection tests, verify-failure status, path validation, and alias cleanup applied.
- Windows Desktop deployment: copied to `D:\ai-council`, `185 passed, 107 subtests passed`, `py_compile` OK, listener restarted with PID `21484`.
