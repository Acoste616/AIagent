# L4.48 Poke Front And iOS Recipes

L4.48 fixes the visible gap Bartek reported: Telegram should not pretend the system is already Poke-level. It now answers Poke/parity criticism with a short operator diagnosis, current P0 gaps, and one next move. It also adds a concrete iPhone Shortcuts recipe pack so the iPhone path stops being abstract setup text.

## What Changed

- `POKE_GAP_VERSION` is now `L4.48`.
- `POKE_FRONT_VERSION` remains `L4.44` for One Contact Memory Front.
- `SHORTCUTS_VERSION` is now `L4.48`.
- `/poke-gap` and natural feedback such as `nie odpowiada jak Poke`, `nie ma takich możliwości`, or `gdzie ten cel` now return:
  - decision that parity is not done,
  - current facts,
  - P0 gaps,
  - current runtime counts,
  - one next move.
- `/shortcuts recipes`, `/shortcuts cookbook`, `iphone recipes`, and `payloady shortcuts` return a concrete iOS Shortcut cookbook.
- `/shortcuts` now points to both `/shortcuts setup` and `/shortcuts recipes`.

## iOS Recipe Pack

The cookbook exposes six read-only/capture recipes:

- `ask_council`
- `share_url_research`
- `voice_note_to_task`
- `screenshot_to_task`
- `agent_inbox_status`
- `task_status`

Each recipe includes:

- method: `POST`,
- URL: current `/shortcut` endpoint,
- header placeholder: `X-AI-Council-Token: <token>`,
- compact JSON body,
- R0 safety note.

## Safety

- No token is printed or generated.
- No `.env` write is performed.
- No Shortcuts listener is started automatically.
- No port is opened.
- `approve`, `deny`, `cancel`, and write actions remain blocked from iOS Shortcuts and stay behind Telegram approval.

## Verification

- `python3 -m py_compile ai_council.py`
- `python3 -m pytest tests/test_ai_council.py -q -k 'shortcut or shortcuts or poke_gap or natural_intents or goal'`
- `python3 -m pytest tests/test_ai_council.py -q`
- Local smoke:
  - `Ani nie odpowiada on jak poke nie ma takich możliwości, o co chodzi gdzie ten cel ?`
  - `/shortcuts recipes`
  - `payloady shortcuts`
