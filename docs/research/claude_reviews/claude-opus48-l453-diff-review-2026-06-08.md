I've traced the full delivery path end-to-end. Here's my review.

## Review — L4.53 Recipe Test Follow-up

**Verified working (the things most likely to break):**
- The activation marker survives into delivery. `run_recipe_background` sets `result["summary"]` (ai_council.py:5862) → `save_task_artifacts` preserves it via `result.get("summary")` (ai_council.py:4069) → `run_background_job` reads `artifact["summary"]` (ai_council.py:11412/11420) → `background_delivery_reply_markup` detects the marker. Integration is sound even though no test exercises this whole chain.
- Callback dispatch is correct: `data.split(":",1)` (ai_council.py:13950) maps `recipe-test:health_digest` → handlers at 13980-13988. All four prefixes (`recipe-test/enable/show/list`) resolve.

### BLOCKERS
None. Safety is preserved and the feature works end-to-end.

### NON_BLOCKERS
1. **Marker regex matches arbitrary task content** — `background_delivery_reply_markup` (ai_council.py:11982) runs `\bactivation:\s*recipe\s+(...)` against *every* background summary, including normal research/document tasks. If task content contains the phrase "activation: recipe X", a normal task gets Enable/Test buttons for an arbitrary `X`. Not a safety bypass (Enable is operator-clicked and still re-gated), but it mislabels unrelated output. Minimal fix: anchor to the block this feature emits, e.g. require the header — `if "[Council] Recipe Test Follow-up" in response and (m := re.search(...)):` — so only the appended block triggers recipe buttons.

2. **No per-step success check** — the step loop (ai_council.py:5823-5834) never marks a test as failed; any policy-clean test is "zakończony" and gets the Enable button even if a step's `build_response` returned an error string. Unsafe recipes are still correctly blocked early with `status:"blocked"` (ai_council.py:5811-5820) and never reach the follow-up block, so this is UX-only, not a safety hole. Optional: gate the follow-up on outputs being error-free.

3. **Recipe card drops Status/Cancel/Actions** — `recipe_task_delivery_reply_markup` (ai_council.py:11943) keeps Details/Facts/Next but omits the Status/Actions buttons that `task_delivery_reply_markup` has. Acceptable (task is complete at delivery) but a behavior delta worth a conscious sign-off.

4. **Test coverage gaps** — the new test calls `run_recipe_background` + `background_delivery_reply_markup` directly. Missing: (a) a normal/non-recipe summary yields `task_delivery_reply_markup` with **no** Enable button, and (b) a policy-blocked recipe test gets **no** Enable button. (b) is the safety-adjacent property and is the one I'd want guarded before deploy. Callback-length fallback (ai_council.py:11946) is also untested.

### VERDICT
**Ship after fixes.** No hard blockers — the feature is correct and safe. I recommend two cheap changes before deploy: the marker anchoring (#1) to stop false positives on unrelated tasks, and a regression test that a blocked recipe test produces no Enable button (#4b).

Want me to apply those two fixes? (I'm in plan mode, so I'll need approval to edit.)

## Host Follow-up

Codex applied both recommended pre-ship fixes after this review:

- `background_delivery_reply_markup` now requires the explicit
  `Recipe Test Follow-up L4.53` header before attaching recipe buttons, so
  unrelated task text containing `activation: recipe ...` cannot produce a
  false recipe card.
- Tests now cover unrelated activation text and blocked recipe-test summaries
  to ensure they do not show `Enable`.
