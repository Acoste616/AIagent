# L4.58 Grok Budget Hygiene

## Purpose

Bartek confirmed that real xAI/Grok usage is still very low. The runtime had an old open improvement saying `Grok daily call limit reached: 20/20`, which could mislead the autonomous loop even after the effective limit was raised.

## Changes

- Added `GROK_BUDGET_HYGIENE_VERSION = "L4.58"`.
- `/cost` now reports current Grok guard state:
  - allowed yes/no
  - calls used today
  - active call limit sources
  - estimated usage
  - active budget limit sources
- `/improve repair` now dismisses stale Grok daily-limit blocked improvements when the current guard allows Grok calls.
- The same stale cleanup also covers old Grok estimated-budget blocked improvements when the current guard allows calls.
- The proactive cost nudge now uses the same operator limit sources as the real guard, including `AI_COUNCIL_GROK_DAILY_CALL_LIMIT`.
- Proactive budget ratio now uses non-blocked usage plus calibrated Grok estimates, matching the real guard instead of counting old blocked rows.

## Safety

- No automatic Grok call is made.
- No env values or secrets are modified.
- Stale blocked improvements are dismissed only when `operator_call_allowed("grok")` currently returns allowed.

## Verification

- Regression test proves `/cost` shows the current `GROK_DAILY_CALL_LIMIT:200` and `GROK_DAILY_BUDGET_USD:$5.0000`.
- Regression test dismisses stale `Grok daily call limit reached: 20/20` and stale Grok estimated-budget blocked items only when the current guard allows Grok calls.
- Regression test keeps the item open when the guard still blocks Grok.
