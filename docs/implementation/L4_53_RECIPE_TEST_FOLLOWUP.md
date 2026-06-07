# L4.53 Recipe Test Follow-up

## Goal

L4.52 made recipe creation feel more like Poke by adding a Telegram activation
card after approval. L4.53 extends that into the next visible moment: after a
one-off recipe test finishes, the final Telegram task delivery keeps the recipe
activation actions in-thread.

This is a small proactivity step: the user does not need to remember how to
enable or inspect the recipe after seeing the test result.

## Behavior

When `/recipe test <name>` completes successfully, the saved task summary now
includes:

```text
[Council] Recipe Test Follow-up L4.53
activation: recipe <name>
state: disabled
enable: /recipe enable <name>
test_again: /recipe test <name>
show: /recipe show <name>
```

Final Telegram delivery uses combined buttons:

- `Test`
- `Enable`
- `Show`
- `Details`
- `Facts`
- `Next`

Non-recipe background tasks keep the normal task delivery buttons.

## Safety

- `test` still runs only one time and does not enable the schedule.
- unsafe recipe steps remain blocked by `recipe_step_violations`.
- scheduled execution still requires explicit `Enable`.
- final delivery only changes the buttons and summary text; it does not perform
  provider writes, shell execution, contacts, publishing, payments, DNS/auth, or
  deletion.

## Verification

Local and Windows:

```bash
python3 -m py_compile ai_council.py
python3 -m pytest tests/test_ai_council.py -q -k "recipe_test_followup or recipe_activation or recipe_test or true_poke_target"
python3 -m pytest tests/test_ai_council.py -q
```

Expected:

- recipe test result includes `Recipe Test Follow-up L4.53`;
- background delivery markup contains recipe activation buttons and task detail
  buttons;
- `/health` includes `recipe_test_followup=L4.53`.
