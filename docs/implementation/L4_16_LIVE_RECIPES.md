# L4.16 Live Recipes

Date: 2026-06-07

## Goal

Move AI Council closer to Poke-like behavior by making natural Telegram intents select real reusable recipes, not just one-off routes.

This is still not full Poke parity. It is the first live recipe routing layer.

## Implemented

- Action Planner now selects deterministic live recipes when the intent matches known workflows.
- New planner-selectable recipes:
  - `gmail_context_brief`
  - `calendar_context_brief`
  - `drive_context_brief`
- Existing recipes now expose metadata for selection:
  - `research_brief`
  - `daily_system_digest`
  - `error_audit_twice_daily`
  - `feature_evolution_loop`
  - `project_next_action`
  - monitors for stuck tasks and costs
- New command:
  - `/recipe suggest <intent>`
- New command:
  - `/loops`
- Natural loop routing:
  - `pokaż pętle`
  - `sprawdź pętle`
  - `loops`

## Behavior

Examples:

```text
ogarnij mi research Poke
-> /plan-action
-> live_recipe: research_brief
-> /recipe run research_brief ...
```

```text
przygotuj mi raport z gmail o Poke
-> /plan-action
-> live_recipe: gmail_context_brief
-> /recipe run gmail_context_brief ...
```

```text
wyślij maila do klienta
-> pending approval
```

## Safety

- Side-effect verbs still force approval.
- Gmail/Calendar/Drive matching is read-only and goes through connector sync/brief recipes.
- Recipe steps are deny-by-default:
  - unknown commands are blocked;
  - `/write`, `/append`, `/patch`, `/execute`, `/approve`, `/deny`, `/rollback` are not allowed inside recipes;
  - `/connector`, `/source`, and `/memory` are restricted to read-only actions.
- External write/send/schedule/publish/delete/billing/DNS/auth remains blocked without approval.
- Recipe selection is deterministic and testable; it does not block Telegram on model routing.

## Verification

Local:

```text
python3 -m py_compile ai_council.py tests/test_ai_council.py
git diff --check
python3 -m unittest tests/test_ai_council.py
```

Result:

```text
Ran 129 tests
OK
```

Covered by tests:

- default live recipes exist and are planner-selectable;
- Action Planner routes research to `research_brief`;
- Action Planner routes Gmail read-only requests to `gmail_context_brief`;
- side-effect mail request still creates pending approval;
- `/recipe suggest` returns matched recipe;
- `/loops` shows error and feature-evolution loops;
- natural `pokaż pętle` routes to `/loops`.
- unsafe recipe steps are blocked and recorded in the error log.
