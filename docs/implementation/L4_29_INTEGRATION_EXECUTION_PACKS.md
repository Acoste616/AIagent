# L4.29 Integration Execution Packs

Date: 2026-06-07

## Purpose

L4.29 closes the most visible gap after L4.28 drafts: an approved integration draft can now move through a concrete local execution step instead of stopping at "approved".

This is still not provider write execution. The layer creates a local outbox pack only.

## User Flow

1. Create a draft:
   `/connector draft gmail|calendar|drive|github <intent>`
2. Inspect it:
   `/drafts show <action_id>`
3. Approve it:
   `/approve <action_id>`
4. Create the local execution pack:
   `/execute <action_id>`
5. Verify the pack:
   `/verify <action_id>`

## What `/execute` Does

For `integration_draft` actions with status `approved` or `verify_failed`, `/execute <action_id>` writes:

- `artifacts/integration-outbox/<action_id>/execution_pack.json`
- `artifacts/integration-outbox/<action_id>/execution_pack.md`

The pack includes:

- action id,
- connector,
- draft kind,
- original intent,
- missing fields,
- draft payload,
- `provider_action: manual_outbox_pack`,
- `external_write: false`,
- safety policy,
- next steps.

It also records the pack path in project memory as `integration-pack:<action_id>`.

Already `executed` actions are not re-written; the next step is `/verify <action_id>`.
Already `verified` actions cannot be re-executed, because that would overwrite the audited pack. Create a new draft for changes.

## What `/execute` Does Not Do

It does not:

- send email,
- create calendar events,
- write Drive files,
- open GitHub issues,
- publish,
- contact anyone,
- spend money,
- change provider state.

That remains blocked until L4.30 Provider Execution Adapters.

## Verification

`/verify <action_id>` checks:

- execution pack JSON exists,
- execution pack Markdown exists,
- JSON parses correctly,
- action id matches,
- connector matches,
- pack and payload both say `external_write: false`,
- provider action is exactly `manual_outbox_pack`.

If all checks pass, the action becomes `verified` and durable verifier evidence is appended to `actions.jsonl`.

## Why This Matters For Poke Parity

Poke-like behavior needs the user to feel forward motion after approval. L4.28 produced structured drafts, but approval still felt like a dead end. L4.29 turns approval into an auditable local handoff artifact, which is the safe bridge toward real provider adapters.

## Remaining Gap

L4.29 is not full Poke parity. The next missing layer is L4.30:

- Gmail send/draft adapter with explicit review gate,
- Calendar event adapter with preview and undo/cancel semantics where possible,
- Drive document/file adapter,
- GitHub issue/PR adapter,
- per-connector verifier and rollback/undo policy,
- provider-write audit trail with source references.

## Verification Status

- Mac local tests: `179 passed` + `py_compile` + `git diff --check`.
- Claude review: complete; fixed the main audit issue by blocking pack overwrite after `verified`.
- Windows Desktop deployment: copied to `D:\ai-council`, `179 passed, 107 subtests passed`, `py_compile` OK, listener restarted with PID `4260`.
