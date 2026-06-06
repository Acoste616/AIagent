# AI Council L2.7 Recipe Scheduler Implementation

Date: 2026-06-06
Target runtime: `D:\ai-council` on Windows Desktop

## Outcome

L2.7 extends the Poke-like recipe layer from a manual MVP into a small recurring
automation layer. Recipes can now be enabled or disabled, scheduled recipes are
started by the always-on service loop, and each scheduled window is recorded so
the bot does not repeatedly start the same recipe.

## Implemented

- `/recipe enable <name>`
- `/recipe disable <name>`
- Recipe trigger metadata:
  - `{"type": "manual"}`
  - `{"type": "schedule", "cron": "30 8 * * *"}`
  - `{"type": "schedule", "interval_seconds": 1800}`
- Scheduler loop in `serve` and bounded `listen`.
- `recipe_runs.jsonl` ledger for idempotency per recipe/window.
- Manual scheduler check command: `python -X utf8 ai_council.py run-scheduler`.
- Default recipe catalog expanded to:
  - `research_brief`
  - `daily_system_digest`
  - `project_next_action`
  - `stuck_tasks_monitor`
  - `cost_usage_monitor`

## Defaults

- `daily_system_digest`: enabled, scheduled for `30 8 * * *`.
- `research_brief`: enabled, manual.
- `project_next_action`: enabled, manual.
- `stuck_tasks_monitor`: disabled by default to avoid Telegram noise.
- `cost_usage_monitor`: disabled by default to avoid Telegram noise.

## Verification

Local repository:

```text
Ran 46 tests
OK
```

Windows Desktop:

```text
Ran 46 tests
OK
```

Windows status after deployment:

```text
Bartek AI Council Telegram: Running
Capabilities L2.7 active
running_tasks: 0
stuck_tasks: 0
codex: OK
claude: OK
claude_flow: OK model=claude-opus-4-8 mode=plan
grok: OK
```

Scheduler smoke check:

```text
scheduled_recipes_started=0
```

Recipe management smoke check:

```text
Recipe `cost_usage_monitor` enabled.
Recipe `cost_usage_monitor` disabled.
False
```

## Boundaries

This does not introduce shell execution, external writes, contacts, publishing,
money movement, DNS/auth/billing changes, or destructive actions. Scheduled
recipes only run through the existing AI Council routing and background task
machinery.
