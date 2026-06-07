# L4.54 Grok X+Web Research

## Purpose

Bartek confirmed that Grok usage is still low enough to use it more aggressively for the Poke/OpenClaw/Hermes build loop. The previous `/xresearch` path used only `x_search` and had a default `to_date` cutoff of `2026-06-06`, which could miss newer public signals.

## Changes

- Added `GROK_RESEARCH_VERSION = "L4.54"`.
- Added dynamic research date range:
  - default `from_date`: `2026-03-01`
  - default `to_date`: current UTC date
- Added `grok_research_tools()`:
  - always includes `x_search`
  - includes `web_search` by default
  - `AI_COUNCIL_GROK_WEB_SEARCH_ENABLED=false` can disable web search if needed
- Updated `/poke-research` prompt language from X-only to X+web.
- Updated `/health`, `/goal`, `/status`, `/selftest`, and `/capabilities` version text.

## Verification

- Unit test asserts the xAI Responses payload includes `x_search`, `web_search`, and a current `to_date`.
- Existing `/delegate prepare` path still uses `grok_x_research_response`, so Claude receives the expanded research pack without changing the delegate workflow.

