# L4.51 Recipe Creator v0

## Goal

Grok's 2026-06-07 Poke mechanics research picked Recipes as the next highest
Poke-parity feature after L4.50 front quality logging.

L4.51 adds a small Telegram-native Recipe Creator:

- Bartek can write `stwórz recipe ...` or `/recipe create ...`.
- AI Council creates a readable recipe preview in the same thread.
- The recipe is not saved until Bartek approves the pending action.
- The saved recipe is disabled by default and can be reviewed or run manually.

This copies the Poke mechanic of creating reusable workflows in chat without
adding unsafe external writes.

## Behavior

Examples:

```text
stwórz recipe codziennie o 8 health digest
```

Creates a pending action with:

- generated recipe name,
- trigger preview,
- one read-only step,
- risk `R1` because approval writes a local recipe JSON file,
- inline approval buttons.

Approval:

```text
/approve act-...
```

Saves the recipe JSON under `recipes/`, keeps `enabled=false`, and reports:

```text
show: /recipe show <name>
run: /recipe run <name> <input>
external_write_performed: false
```

## Supported v0 Intents

The creator maps simple intents to safe steps:

- system status -> `/health`
- errors/debug -> `/errors recent 10`
- usage/cost -> `/cost`
- Gmail read-only brief -> `/connector brief gmail {input}`
- Calendar read-only brief -> `/connector brief calendar {input}`
- Drive read-only brief -> `/connector brief drive {input}`
- research/Poke/X -> `@xresearch {input}`
- fallback digest -> `/chat Podsumuj jako krótki digest: {input}`

Schedules:

- `codziennie o 8` -> cron `0 8 * * *`
- `co 30 minut` -> interval `1800`
- `co godzinę` -> interval `3600`
- otherwise manual trigger.

## Safety

Blocked in v0:

- sending email,
- calendar event creation,
- contacting customers,
- publishing,
- payment/money,
- delete/DNS/auth/billing,
- local file write/patch recipes.

Recipe Creator also refuses to create or approve a recipe whose generated name
already exists. This prevents accidental overwrite of system recipes such as the
autonomous error-audit and feature-evolution loops.

External write actions still use the existing draft/approval/provider gate
paths, not Recipe Creator.

## Verification

Local:

```bash
python3 -m py_compile ai_council.py
python3 -m pytest tests/test_ai_council.py -q -k "recipe_creator or true_poke_target"
python3 -m pytest tests/test_ai_council.py -q
```

Smoke after deploy:

```powershell
py -3 ai_council.py respond "stwórz recipe codziennie o 8 health digest"
py -3 ai_council.py respond "/health"
```

Expected:

- create response includes `Recipe Creator L4.51`, `Pending action utworzona`, and an `act-...` id;
- `/health` includes `recipe_creator=L4.51`.
