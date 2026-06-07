# L4.21 Unified Front Orchestrator

Date: 2026-06-07

## Goal

Make Telegram feel like one operator instead of exposing raw `Codex`, `Claude`, and `Grok` labels in direct replies.

## Implemented

- Added a host-facing wrapper for direct operator routes:
  - `@codex`
  - `codex_default`
  - `@claude`
  - `@claude-flow`
  - `/flow`
  - `@grok`
  - `@research`
  - `@xresearch`
  - `/xresearch`
  - `/poke-research`
- Direct Telegram responses now start with `[Council]` and a human-readable status such as:
  - `Odpowiedź gotowa`
  - `Research gotowy`
  - `Plan workflow gotowy`
- `@all` now returns one host-style consultation summary instead of three raw operator blocks.
- Background direct-operator tasks keep raw operator output in `raw_output` and `report`, while Telegram summary stays host-wrapped.
- `/goal`, `/status`, `/selftest`, and `/capabilities` now report L4.21.

## Why It Matters

Poke-like interaction should feel like a single assistant operating a tool bench, not like a user manually reading three separate model transcripts. L4.21 keeps the internal multi-operator architecture but makes the default Telegram experience more unified.

## Remaining Gap

This is not a full agent OS yet. Remaining Poke-level gaps include:

- durable project memory spine;
- richer live streaming/progress for long model calls;
- iPhone Shortcuts as primary capture;
- private iMessage bridge;
- write-capable external connectors after approval.

## Verification

Expected local and Windows result:

```text
Ran 152 tests
OK
```
