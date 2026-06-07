# L4.30 Provider Adapter Manifests

Date: 2026-06-07

## Purpose

L4.30 adds the missing bridge between a verified local integration pack and future write-capable provider execution.

It does not send email, create events, write Drive files, or open GitHub issues. It creates a provider adapter manifest that explains exactly what would be needed to do that safely.

## User Flow

1. Create an integration draft:
   `/connector draft gmail|calendar|drive|github <intent>`
2. Approve it:
   `/approve <action_id>`
3. Create a local execution pack:
   `/execute <action_id>`
4. Verify the local pack:
   `/verify <action_id>`
5. Create provider handoff manifest:
   `/provider plan <action_id>`
6. Inspect or verify:
   `/provider show <action_id>`
   `/provider verify <action_id>`

`/provider execute <action_id>` is present but intentionally blocked in L4.30.

## Manifest Contents

The manifest is written to:

- `artifacts/provider-adapters/<action_id>/provider_manifest.json`
- `artifacts/provider-adapters/<action_id>/provider_manifest.md`

It includes:

- connector,
- provider operation,
- HTTP method,
- endpoint,
- required scopes,
- auth type and readiness,
- draft payload,
- missing fields,
- execution pack readiness,
- `external_write_performed: false`,
- `write_gate: disabled_l4_30_manifest_only`.

## Supported Adapter Contracts

- Gmail: `gmail.users.drafts.create`
- Calendar: `calendar.events.insert`
- Drive: `drive.files.create`
- GitHub: `github.issues.create` with classic `repo` scope or fine-grained `Issues: Write` permission.

These are contracts only. No provider state is changed in L4.30.

## Status Values

- `blocked_not_verified`: integration draft has not completed `/verify`.
- `blocked_missing_fields`: draft still has unresolved required fields.
- `blocked_auth`: connector auth is not configured.
- `ready_write_gate_disabled`: draft/auth look ready, but provider writes are still disabled.
- `ready_for_future_provider_write`: reserved for a future explicit write layer.

## Safety Contract

L4.30 preserves the same no-write guarantee as L4.29:

- no email is sent,
- no calendar event is created,
- no Drive file is created,
- no GitHub issue is opened,
- no external write happens.

Future L4.31 must add a separate confirmation gate, provider-specific verifier, and rollback/undo policy before any real write-capable adapter can run.

## Verification

- Mac local tests: `182 passed` + `py_compile` + `git diff --check`.
- Claude review: complete; safety contract approved with minor cleanup applied.
- Windows Desktop deployment: copied to `D:\ai-council`, `182 passed, 107 subtests passed`, `py_compile` OK, listener restarted with PID `6984`.
