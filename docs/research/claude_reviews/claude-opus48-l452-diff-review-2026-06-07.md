## Review — L4.52 Recipe Activation Card

Reviewing the diff only. No hard correctness blocker found that breaks the safety model, but two items should be fixed before ship.

### BLOCKERS

**1. Callback target vs. stored name mismatch — `recipe_activation_reply_markup` / `handle_callback_query`** (`ai_council.py`)
Button data is built from `safe_filename(name, "recipe")[:48]`, but the callback handlers (`recipe_enable_response`, `recipe_test_response`, `recipe-show`) pass that token straight into `load_recipe(target)` / `set_recipe_enabled(target, …)`. If a Recipe Creator name contains chars that `safe_filename` rewrites, or exceeds 48 chars, the Test/Enable/Show buttons resolve to a name `load_recipe` can't find → silent "Nie znalazłem recipe". This is the *primary* path users hit after approval.
Minimal fix: slug/clamp the recipe name to the same canonical form at *creation/save* time so `recipe["name"]`, `recipe_path()`, and the callback token are always identical; or in the markup, assert `recipe_path(name).stem == safe_name` and fall back to a `recipe-list` button when truncated. Add a test with a long/space-containing name that round-trips create→approve→callback enable.

**2. No test that `test` mode cannot run an unsafe recipe** (`tests/test_ai_council.py`)
`run_recipe_background` skips the `enabled is False` gate when `action == "test"`, then relies on `recipe_step_violations` to block bad steps. That allowlist check is the *only* thing standing between "disabled test" and executing a non-read-only step. There is a creation-time block test, but nothing asserts the test path itself rejects a violating recipe. Add: save a disabled recipe with an out-of-allowlist step, call `run_recipe_background("test <name>")`, assert it's blocked and nothing executed. Without this, a regression in violation ordering ships silently.

### NON_BLOCKERS

1. **Limit check skips recipes with missing `enabled` field.** Both `active_custom_recipe_count` (`recipe.get("enabled") is False`) and `recipe_activation_blockers` (`recipe.get("enabled") is False`) use identity-against-`False`. A custom recipe with `enabled` absent/`None` neither counts toward nor is gated by the limit. Creator saves `enabled: False`, so it's edge-only — but normalize to `bool(recipe.get("enabled"))` for safety.

2. **`set_recipe_enabled` now runs `recipe_step_violations` on every enable, including live/non-custom recipes.** Behavior change vs. prior (enable had no violation check). Desirable for safety, but could block enabling a previously-enableable live recipe if its steps trip the allowlist. Confirm live recipes' steps all pass `recipe_step_violations`.

3. **Activation card re-attaches on enable success.** `set_recipe_enabled` enable response contains `activation: recipe {name}`, so `response_reply_markup` re-renders Test/Enable/Show — an "Enable" button on an already-enabled recipe. Clicking it re-saves harmlessly, but it's confusing UX. Consider an enabled-state variant without the Enable button.

4. **Test-button task spam window.** `recipe_test_response` idempotency key is per-minute (`time.time()//60`); rapid double-taps inside one minute dedupe, but the callback still calls `start_background_job` after `create_task` — verify `start_background_job` is a no-op when `create_task` returns an existing task, otherwise repeated taps across minute boundaries each spawn a job. Telegram resends unacked callbacks, so confirm dedup actually suppresses the second run.

5. **`approve_response` dropped the `/recipe run` hint.** Only the activation summary remains; run still works but is now undiscoverable from the approval card. Cosmetic.

### Safety assessment (per focus areas)
- **Disabled/scheduled run without Enable:** Scheduler path still uses `run` → `enabled is False` gate intact; only explicit `test` bypasses it as a one-off. ✅
- **Unsafe enable/test:** Both gated by `recipe_step_violations`; enable additionally limit-gated. ✅ (but see Blocker 2 — untested).
- **Callback routing:** Enable→`set_recipe_enabled` (full policy), Test→violations-checked, Show→read-only. No policy bypass. ✅ (modulo Blocker 1 name resolution).
- **Idempotency:** Per-minute key present; confirm `start_background_job` honors it (Non-blocker 4).
- **Regression:** `/recipe run`, enable/disable, health/status/selftest strings updated and covered. ✅

### VERDICT
**Ship after fixes** — resolve Blocker 1 (callback name resolution) and Blocker 2 (unsafe-test regression test); the rest are non-blocking hardening.
