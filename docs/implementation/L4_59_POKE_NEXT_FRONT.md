# L4.59 Poke Next Front

## Purpose

The Telegram front still felt too much like a system dashboard for ordinary messages. Live checks showed:

- `co dalej` returned the full Agent Inbox instead of one operator-style next move.
- `czy możesz zrobić research poke...` fell back to generic `/chat` instead of starting Poke research.
- `napisz mi krótkie podsumowanie statusu` fell back to generic chat and could surface stale conversation context.

## Changes

- Added `POKE_NEXT_FRONT_VERSION = "L4.59"`.
- Natural `co dalej` / `co teraz` routes to `/agent next`.
- `/agent next` returns a compact operator card:
  - decision,
  - one-line facts,
  - one `NEXT`,
  - optional safe `RUN`.
- Natural research questions starting with `czy możesz... research` route to:
  - `/poke-research` when the topic mentions Poke,
  - `@research` otherwise.
- Natural status-summary requests route to `/front` instead of generic chat.
- Status-summary requests return a compact `[Council] Status L4.59` card instead of the full `/front` diagnostic.
- Direct `/chat co dalej` uses the same compact Agent Next response.

## Safety

- No new external write.
- No daemon start.
- Research routes still use existing background task/idempotency/progress handling.
- R3/R4 approval gates remain unchanged.

## Verification

- Regression test for compact `co dalej`.
- Regression test for Poke research question routing to background `/poke-research`.
- Regression test for status summary routing to `/front`.
- Regression test for compact status summary response.
