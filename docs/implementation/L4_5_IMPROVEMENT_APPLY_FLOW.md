# L4.5 Improvement Apply Flow

Date: 2026-06-07

## Goal

Close the loop between autonomous improvement candidates and actionable implementation planning.

Before this layer, `feature_evolution_loop` and `error_audit_twice_daily` could write backlog items, but Codex still had to manually copy the item into a planning task.

## Change

New background-capable commands:

- `/improve plan <improvement_id>`
- `/improve apply <improvement_id>`

Both commands:

- require a background task;
- create an AI Council planning artifact from the selected improvement;
- mark the improvement as `planned`;
- attach `plan_task_id`;
- update `next_action` to point at `/details <task_id>` and `/improve done <id>`.

This does not execute file writes automatically. It converts:

```text
improvement candidate -> structured Council implementation plan
```

Actual code changes still happen through Codex audit, tests, and explicit implementation work. External writes and destructive actions remain blocked by the existing approval/risk layer.

## Telegram Flow

```text
/improvements
/improve show imp-...
/improve apply imp-...
/details task-...
/improve done imp-...
```

## Verification

Local:

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -X utf8 tests/test_ai_council.py`
- result: 74/74 OK

Covered by tests:

- `/improve apply <id>` requires a task;
- `/improve apply <id>` runs in background;
- `/improve show <id>` stays foreground;
- `run_improve_background()` calls structured Council planning;
- selected improvement is marked `planned`;
- `plan_task_id` is saved;
- result links to `/details <task_id>` and `/improve done <id>`.
