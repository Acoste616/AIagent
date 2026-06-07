# Claude Code Task: Poke-Parity AI Council Audit

You are Claude Code acting as a bounded collaborator for Bartek AI Council.

## Context

Repository:

`/Users/bartoszdomanski/Documents/Codex/2026-06-06/https-x-com-interaction-status-2062575428213285352/github-AIagent`

Windows runtime target:

`D:\ai-council`

Current implementation includes:

- Telegram AI Council runtime;
- Poke-style front operator routing for ordinary chat;
- Codex, Claude, Claude Flow Opus 4.8, Grok, Grok X research routes;
- background jobs, task artifacts, Details/Facts/Next;
- recipes and scheduler;
- Risk Officer and approved local workspace write/append/patch;
- media capture and iPhone Shortcuts ingress;
- new L4.3 error store and autonomous loops:
  - `/errors`;
  - `errors/<YYYY-MM-DD>.jsonl`;
  - `state/errors.jsonl`;
  - `error_audit_twice_daily`;
  - `feature_evolution_loop`;
  - recipe `{previous}` chaining.

## Objective

Audit the current system against Bartek's real goal:

Build a private Poke-like but better Agent OS that combines:

- Poke-style messaging-first UX;
- Grok/X research;
- Claude dynamic workflows and planning;
- Codex implementation and verification;
- OpenClaw/Hermes-style local execution;
- iPhone-first capture and future Apple Messages/iMessage channel;
- autonomous improvement loops that find errors, research new features, plan, and feed implementation.

## Task

Do a code-aware council audit and produce a concrete next-iteration plan.

Do not perform external writes, publishing, outbound contact, auth/billing/DNS changes, or destructive actions.

## Output Contract

Return a Polish report with these sections:

1. `WERDYKT`: one paragraph on whether current code is actually Poke-like yet.
2. `BRAKI TOP 10`: missing capabilities, ordered by product impact.
3. `RYZYKA/BŁĘDY`: likely technical failure modes in the current implementation.
4. `NAJBLIŻSZY SPRINT`: one sprint that Codex should implement next, with exact files/functions.
5. `ACCEPTANCE CRITERIA`: concrete Telegram/runtime checks proving the sprint works.
6. `TESTY`: exact tests that should be added or updated.
7. `NIE RUSZAĆ JESZCZE`: what should remain out of scope until the core is stable.

Prefer practical code-level recommendations over broad strategy.
