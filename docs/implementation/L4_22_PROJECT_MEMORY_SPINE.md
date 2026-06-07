# L4.22 Project Memory Spine

Date: 2026-06-07

## Goal

Make AI Council remember long-running project work with source-backed entries, not only ad hoc chat memory.

## Implemented

- Existing `memory.sqlite` now supports stable upsert IDs for durable project-memory rows.
- Completed task artifacts write project memory sections:
  - decision;
  - facts;
  - next actions.
- Each project-memory row includes:
  - task id;
  - `/details <task_id>`;
  - source path to the report/artifact.
- Added `/project-memory` command:
  - `/project-memory`
  - `/project-memory search <query>`
  - `/project-memory context <query>`
  - `/project-memory rebuild [limit]`
- Natural routing:
  - `pamięć projektu`
  - `szukaj w pamięci projektu <query>`
- Operator auto-recall now prioritizes project memory and includes source references before general memory.
- Recipes can read `/project-memory recent/search/context`, but cannot call `/project-memory rebuild`.

## Why It Matters

Poke-like behavior needs continuity. L4.22 makes completed work feed future work automatically, while still preserving source references so the assistant can say where the memory came from.

## Remaining Gap

This is not full long-term personal memory yet. Remaining work:

- budget reservation before high-concurrency model calls;
- richer streaming/progress for long model calls;
- iPhone capture as primary input;
- private iMessage bridge;
- write-capable external connectors after approval.

## Verification

Expected local and Windows result:

```text
Ran 155 tests
OK
```
