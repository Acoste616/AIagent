# L4.43 Autonomous Loop Cadence

L4.43 closes the practical gap where AI Council had autonomous recipes, but the goal loop still felt passive.

## What Changed

- `feature_evolution_loop` now runs twice daily at `10:15` and `22:15`.
- `error_audit_twice_daily` and `feature_evolution_loop` have `recipe_version=L4.43` and `cadence=twice_daily`.
- Existing stale recipe JSON files are migrated on startup by `ensure_default_recipes()`.
- Migration updates managed loop fields while preserving the user's `enabled` flag.
- `/loops` now reports `L4.43`, cadence, next two scheduled windows, and last run.
- `/health`, `/selftest`, `/goal`, `/capabilities`, and Poke Gap responses expose the cadence layer.

## Why

Bartek's goal requires two autonomous loops that keep the Poke-like system improving:

- error loop: inspect Telegram/runtime errors and ask Claude Flow for fixes;
- evolution loop: use Grok/X research and Claude Flow planning to create the next implementation candidate.

Before L4.43, the evolution loop was only daily and existing deployed recipe files could keep stale schedules. That made the system look implemented in code but passive in practice.

## Safety

- Loops still run as read-only recipes.
- External writes remain behind approval/provider gates.
- `/control pause scheduler` or `/control kill` stops scheduled recipes.
- Idempotency remains per recipe/window in `state/recipe_runs.jsonl`.

## Verification

- Unit tests cover:
  - two due windows for `feature_evolution_loop`;
  - migration from stale recipe JSON to L4.43 while preserving `enabled=false`;
  - `/loops` showing cadence and next windows.
