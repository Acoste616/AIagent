# L4.52 Recipe Activation Card

## Goal

Grok's 2026-06-07 activation research found that Poke Recipes feel strong
because creation is followed by immediate activation and proactive follow-up in
the same messaging thread.

L4.52 narrows that into a safe Telegram implementation:

- keep explicit approval before saving a recipe;
- after approval, show a Telegram-native activation card;
- allow one-off `Test` without enabling the schedule;
- allow `Enable` only after policy validation;
- cap active custom recipes to avoid latency/cost drift.

## Behavior

After:

```text
stwórz recipe codziennie o 8 health digest
/approve act-...
```

AI Council now responds with:

```text
[Council] Recipe Activation L4.52
DECYZJA: recipe `health_digest` jest zapisana, jeszcze nieaktywna.
activation: recipe health_digest
active_custom_recipes: 0/5
test: /recipe test health_digest
enable: /recipe enable health_digest
show: /recipe show health_digest
```

Telegram inline buttons:

- `Test` -> one-off background run using `/recipe test <name>`;
- `Enable` -> validates policy and enables the recipe;
- `Show` -> displays recipe details;
- `Recipes` -> lists recipes.

## Safety

Approval still only saves the recipe. It does not enable scheduled execution.

`/recipe test <name>` can run a disabled recipe once, but it still goes through
the read-only recipe allowlist.

`/recipe enable <name>` blocks when:

- recipe steps violate read-only recipe policy;
- the recipe is custom-created and the active custom recipe limit is reached.

Default custom active limit:

```text
AI_COUNCIL_RECIPE_ACTIVE_LIMIT=5
```

System recipes such as autonomous error-audit and feature-evolution loops do
not count toward the custom recipe limit.

## Verification

Local and Windows:

```bash
python3 -m py_compile ai_council.py
python3 -m pytest tests/test_ai_council.py -q -k "recipe_activation or recipe_test or recipe_creator or true_poke_target"
python3 -m pytest tests/test_ai_council.py -q
```

Smoke:

```powershell
py -3 ai_council.py respond "stworz recipe codziennie o 8 o nazwie smoke_l452_test health digest"
py -3 ai_council.py respond "/approve act-..."
py -3 ai_council.py respond "/health"
```

Expected:

- approval response includes `Recipe Activation L4.52`;
- response has activation markup with `Test`, `Enable`, `Show`;
- `/health` includes `recipe_activation=L4.52`.
