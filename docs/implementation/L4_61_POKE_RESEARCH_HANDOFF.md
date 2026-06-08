# L4.61 Poke Research Handoff

## Purpose

L4.60 made natural Poke/OpenClaw/Hermes build intent start Grok `/poke-research`. The next gap was that a completed research task could still end as a report only.

L4.61 turns successful Poke research into a pending Claude Flow handoff, so the loop becomes:

`Grok X+web research -> pending Claude Opus 4.8 plan -> host audit/implementation`

## Changes

- Added `POKE_RESEARCH_HANDOFF_VERSION = "L4.61"`.
- Successful background `/poke-research` now attaches an explicit follow-up proposal:
  - command: `/flow`
  - risk: `R0`
  - prompt includes the task id and the saved `raw.md` / `report.md` artifact paths.
- Failed/blocked `/poke-research` does not create a Claude handoff.
- Final task summary appends the actual `Follow-up ready: /approve act-...` line even when the operator supplied a custom summary.
- Background delivery markup now shows `Approve follow-up` / `Deny` plus task `Details` / `Facts` / `Next`.
- `/health` exposes `poke_handoff=L4.61`.

## Safety

- No automatic Claude run after Grok.
- No shell execute.
- No external write.
- The follow-up still goes through the existing action approval path and safe follow-up risk checks.

## Verification

- Successful `/poke-research` creates a pending follow-up action with `/flow`.
- Failed `/poke-research` creates no follow-up.
- Delivery markup exposes Approve/Deny and artifact buttons.
