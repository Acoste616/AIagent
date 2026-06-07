# L4.4 Autonomous Improvement Backlog

Date: 2026-06-07

## Goal

Close the gap between autonomous research/planning loops and Codex implementation.

Before this layer, `error_audit_twice_daily` and `feature_evolution_loop` could create artifacts, but there was no single operational queue for "what should Codex implement next".

## Change

New state file:

- `D:\ai-council\state\improvements.jsonl`

New Telegram commands:

- `/improvements`
- `/improve next`
- `/improve show <improvement_id>`
- `/improve done <improvement_id>`
- `/improve dismiss <improvement_id>`

Natural route:

- `pokaż ulepszenia`
- `pokaż backlog`
- `co wdrażać`
- `co wdrożyć`
- `następne wdrożenie`

`/health` now includes:

- `improvements_open`

## Recipe Integration

Recipes can now mark outputs as implementation candidates:

```json
{
  "capture_improvement": true,
  "improvement_policy": {
    "enabled": true,
    "source": "feature_evolution_loop",
    "priority": "P2"
  }
}
```

Enabled by default:

- `error_audit_twice_daily` -> creates P1 backlog candidates from error-audit results;
- `feature_evolution_loop` -> creates P2 backlog candidates from Grok/X research + Claude Flow plans.

Each backlog item stores:

- `improvement_id`
- `status`: `open`, `done`, or `dismissed`
- `priority`
- `source`
- `source_task_id`
- `recipe`
- `title`
- compact `summary`
- `next_action`

## Operating Flow

Target loop:

```text
Grok/X research or error scan
-> Claude Flow plan
-> improvement backlog
-> Codex audits next candidate
-> Codex implements with tests
-> mark /improve done <id>
```

This is still not full autonomous execution. It is the control layer that prevents autonomous loop outputs from disappearing into long artifacts.

## Verification

Local:

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -X utf8 tests/test_ai_council.py`
- result: 72/72 OK

Covered by tests:

- `/improvements` routes to host;
- `/improve next` routes to host;
- natural `pokaż ulepszenia` routes to `/improvements`;
- default autonomous recipes include `capture_improvement`;
- creating, showing, and closing a backlog item works;
- a recipe with `capture_improvement` writes an item to `state/improvements.jsonl`;
- recipe result next actions link to `/improve show <id>`.
