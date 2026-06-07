# L4.57 Improvement Backlog Repair

## Purpose

Older autonomous loop runs created generic backlog titles such as `Research gotowy` because the first research step was used as the title source. L4.55 fixed new loop output, but existing runtime backlog entries still needed an append-only repair path.

## Changes

- Added `IMPROVEMENT_REPAIR_VERSION = "L4.57"`.
- Added `/improve repair` with `preview` support.
- Detects generic improvement titles:
  - `Research gotowy`
  - `Plan workflow gotowy`
  - `[Council] Errors`
  - Grok blocked/daily-limit placeholders
- Reads the source task `raw.md` artifact and reuses loop synthesis to extract the final planning/decision section.
- Updates the improvement by appending a new JSONL row with:
  - repaired title
  - `previous_title`
  - `repair_version`
  - `repaired_at`
  - updated summary and next action

## Verification

- Regression test repairs a stale `Research gotowy` item into the final `Proactive Topic Ownership` decision from `/flow`.
- Regression test verifies specific titles such as the Poke Host gap are not rewritten.
