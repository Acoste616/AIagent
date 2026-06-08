# L4.62 Claude Delegate Handoff

## Purpose

L4.61 made successful Grok Poke research create a pending Claude Flow planning step. The next gap was that an approved Claude plan could still stop at another text report.

L4.62 turns a successful Claude Flow plan from the Poke research chain into a pending Codex worker delegation handoff:

`Grok X+web research -> pending Claude Opus 4.8 plan -> pending Codex worker pack -> host audit`

## Changes

- Added `CLAUDE_DELEGATE_HANDOFF_VERSION = "L4.62"`.
- Successful background `/flow` / `@claude-flow` runs that include the L4.61 handoff marker now attach an explicit follow-up proposal:
  - command: `/delegate`
  - risk: `R1`
  - prompt includes the source task id and saved `raw.md` / `report.md` artifact paths.
- Plain Claude Flow tasks do not create delegate follow-ups.
- `/delegate` is now follow-up executable and routes to `grok`, `claude-flow`, `codex-worker`, and `host`.
- Final task summary appends the actual `Follow-up ready: /approve act-...` line for Claude Flow handoff tasks.
- Background delivery markup now shows Approve/Deny buttons for `Plan workflow gotowy` responses.
- `/health` exposes `claude_delegate=L4.62`.

## Safety

- No automatic delegate pack after Claude.
- No automatic Codex worker run.
- No shell execute.
- No external write.
- The handoff remains behind the existing action approval path.

## Verification

- Successful L4.61-marked `/flow` creates a pending `/delegate` follow-up.
- Approved handoff executes `/delegate` and calls the Codex worker delegation pack builder.
- Plain `/flow` creates no `/delegate` follow-up.
- Telegram delivery markup exposes Approve/Deny plus artifact buttons for Claude Flow handoffs.
