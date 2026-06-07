# L4.17 Follow-up Runner

Date: 2026-06-07

## Goal

Make completed recipes behave more like a personal operator: after a workflow finishes, AI Council should not silently stop. It should create a concrete follow-up proposal with approval boundaries.

This is still not full Poke parity. It closes the gap between a completed recipe and the next actionable step.

## Implemented

- Completed `/recipe run ...` artifacts can now create a `followup_proposal` action.
- Recipe outputs with an improvement candidate create a follow-up route:
  - `/improve apply <improvement_id>`
- Recipe outputs without an explicit follow-up create a safe `/plan-action` continuation proposal.
- Task summaries and `/next <task_id>` include:
  - `Follow-up ready: /approve <action_id> albo /deny <action_id>`
- New command:
  - `/followups`
- Natural route:
  - `pokaż follow-upy`
  - `pokaż followups`
- Delivery cards include an `Actions` button.

## Approval Behavior

- R0/R1 follow-ups on the allowlist can continue after `/approve`.
- Background routes like `/improve apply <id>` start a new task.
- Risk is recomputed from the concrete follow-up route at approval time; a recipe cannot downgrade a risky follow-up by declaring `R0`.
- R3/R4 follow-ups are checkpoint-only:
  - approval is recorded;
  - no external write/send/schedule/publish action is executed.
- Commands outside the follow-up allowlist are not executed.
- Already executed follow-ups are idempotent; repeated `/approve <id>` does not launch a second task.

## Safety

Allowed follow-up commands are limited to planning, read-only, recipe, council, and approved internal workflow routes.

Follow-up chains have a bounded depth:

- default: `AI_COUNCIL_FOLLOWUP_MAX_DEPTH=3`;
- when the limit is reached, the artifact is saved but no new `followup_proposal` is created.

Not allowed inside follow-up execution:

- `/write`
- `/append`
- `/patch`
- `/execute`
- `/rollback`
- `/approve`
- `/deny`
- publish/contact/billing/DNS/auth side effects

## Verification

Local:

```text
python3 -m py_compile ai_council.py tests/test_ai_council.py
python3 -m unittest tests/test_ai_council.py
```

Result:

```text
Ran 136 tests
OK
```

Covered by tests:

- `/followups` routing;
- natural `pokaż follow-upy` routing;
- recipe artifacts create pending `followup_proposal` actions;
- `/next <task_id>` shows approval/deny path;
- approved safe follow-up starts a background task;
- repeated approve is idempotent;
- approved R4 follow-up does not auto-execute.
- declared low-risk follow-up is recomputed as R4 when the prompt implies contact/email;
- follow-up chain depth cap blocks new proposals after the configured limit.
