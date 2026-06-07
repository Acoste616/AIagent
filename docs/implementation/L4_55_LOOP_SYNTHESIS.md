# L4.55 Loop Synthesis

## Purpose

The autonomous loops existed, but their backlog output could be too generic. A real runtime example created an improvement titled `Research gotowy`, because `create_improvement_from_recipe()` extracted the title from the first raw line of a multi-step recipe instead of the final planning decision.

## Changes

- Bumped `AUTONOMOUS_LOOP_VERSION` to `L4.55` so managed loop recipes migrate on deploy.
- Added Grok triage to `error_audit_twice_daily`:
  - `/errors`
  - `@grok` red-team/root-cause triage
  - `/flow` Claude plan based on Grok triage
- Added loop synthesis helpers:
  - `recipe_step_sections()`
  - `markdown_section()`
  - `recipe_improvement_focus_text()`
  - `recipe_improvement_summary()`
- `create_improvement_from_recipe()` now creates backlog titles from the final planning/decision section when available, not from the first generic status line.

## Verification

- Regression test proves `Research gotowy` is not used as the improvement title when the final `/flow` step contains a `## Decyzja` section.
- Default loop recipe tests verify the error loop includes Grok and that stale loop recipe JSON migrates to the new managed version.

