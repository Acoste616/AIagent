# L4.63 Front Brain v2: Cost-Safe Always-On Intent Router

Date: 2026-06-08

## Problem

Front Brain v1 (L4.6) shipped the LLM intent router scaffolding (`llm_route`,
`route_message`, conversation memory) and wired it into the live listener, but
it is non-functional in production:

1. `AI_COUNCIL_LLM_ROUTER` defaults to `False`, so `/health` shows
   `llm_router: off`. With the router off, every natural-language message that
   the deterministic `natural_intent_route()` keyword matcher does not catch
   falls straight to the `/chat` fallback. No LLM intent understanding happens.
2. Even when the flag is on, the cost gate `llm_router_should_try()` was a
   positive allowlist of 24 hardcoded Polish/English keywords. A novel phrasing
   without one of those keywords (e.g. "ciekawi mnie co inni sądzą o tym
   modelu") never reached the router. That is the opposite of Poke's "just talk
   to it" behavior.

## Key insight

The safety boundary is **not** the cost gate. In `llm_route()` the safety is:

- `LLM_ROUTER_ALLOWED_COMMANDS` allowlist (no write/append/patch/execute/
  rollback/approve/deny/delete/publish/contact/billing/auth/DNS);
- `AI_COUNCIL_LLM_ROUTER_MIN_CONF` minimum confidence;
- re-validation of the chosen command through `route_text()`.

`llm_router_should_try()` is purely a **cost gate**. Broadening it does not
reduce safety; it only changes how often a Grok routing call is spent.

## Change

`llm_router_should_try()` is rewritten from a positive-keyword allowlist into a
negative cost filter:

- still requires the enable flag + `XAI_API_KEY`;
- skips cheap **smalltalk** (greetings/thanks/acks) via the new local
  `is_smalltalk()` helper — no Grok call;
- skips ultra-short noise below `AI_COUNCIL_LLM_ROUTER_MIN_CHARS` (default 4);
- otherwise lets the message reach the router, so novel phrasings route by
  intent rather than by fixed keyword.

New helpers:

- `SMALLTALK_PHRASES` — local set of greetings/acks.
- `is_smalltalk(text)` — local, no LLM; true for a single smalltalk phrase or a
  <=2-word message made only of smalltalk tokens.

The allowlist, min-confidence, and `route_text()` re-validation are unchanged.
The budget reservation in `llm_route()` (`reserve_operator_call`) remains the
hard daily cost ceiling.

## Safety invariants (unchanged)

- No new external write, shell execute, deploy, push, or daemon start.
- Router can still only select read/think commands from
  `LLM_ROUTER_ALLOWED_COMMANDS`.
- Side-effect / destructive intents ("usuń wszystkie pliki") are rejected by the
  allowlist and fall back to `/chat`.
- Low-confidence routes fall back to `/chat`.
- The router is still **off by default** (`AI_COUNCIL_LLM_ROUTER=False`).
  Production enablement is a host env decision, not done by this change.

## Verification

Mac:

- `python3 -m py_compile ai_council.py tests/test_ai_council.py` — OK
- `python3 -m pytest -q tests/test_ai_council.py` — 312 passed

New tests:

- `test_llm_router_routes_novel_phrasing_without_trigger_keyword` — a message
  with no legacy trigger keyword now reaches the router and routes to
  `@research` with `route_source=llm` (would fail on the old allowlist gate).
- `test_llm_router_skips_smalltalk_without_grok_call` — "hej", "dzięki",
  "ok spoko" return `/chat` and never call `request_json`.
- `test_is_smalltalk_detects_greetings_but_not_intents` — unit coverage for the
  helper.

Existing router tests (strict-JSON research route, side-effect rejection,
low-confidence fallback, disabled-without-key, default-off, priority order) stay
green.

## Cost-ledger test isolation (L4.63 follow-up fix — 2026-06-08, Claude)

### Problem found during audit

`ai_council.py` freezes its runtime paths at import time:

```python
STATE_DIR  = Path(os.environ.get("AI_COUNCIL_STATE_DIR", PROJECT_DIR / "state"))
COSTS_FILE = STATE_DIR / "costs.jsonl"   # the real cost ledger
```

The router path `route_message -> llm_route -> reserve_operator_call ->
record_operator_usage -> append_jsonl(COSTS_FILE, ...)` therefore writes to
whatever `STATE_DIR` resolved to *at import*. Running the suite from the
production checkout (`D:\ai-council`) appended fake `llm_router` rows straight
into the live `state/costs.jsonl`, corrupting cost data and budget guards.

This L4.63 router broadening makes it worse: the new negative cost gate lets
**any** non-smalltalk message reach `llm_route`, so far more test messages now
hit the reservation path. Three existing router tests
(`test_llm_route_parses_strict_json_and_selects_research`,
`test_llm_route_rejects_side_effect_commands`,
`test_llm_route_low_confidence_falls_back_to_chat`) enabled the router but did
**not** mock `reserve_operator_call`.

### Reproduction (before fix)

Running just those 3 tests appended **6 rows** (`reserved`+`completed` x3) to the
real `state/costs.jsonl`.

### Fix

1. **`tests/conftest.py`** (new) — primary fix. Redirects the writable runtime
   dirs (`AI_COUNCIL_STATE_DIR` and friends) to a per-session temp sandbox
   **before** `ai_council` is imported. pytest loads `conftest.py` before test
   modules, so the frozen path constants pick up the sandbox. A host-set env var
   is never overridden (deliberate host override still wins); `PROJECT_DIR` is
   left at the repo so read-only assets (`recipes/`, `scripts/`) still resolve.
2. **Hermetic router tests** — the 3 legacy tests above now also mock
   `reserve_operator_call`/`finalize_operator_call` (matching the new
   novel-phrasing test), so all router tests are uniform and ledger-independent
   even if the conftest is ever bypassed (defense in depth).

### Verification (after fix)

- `python3 -m py_compile ai_council.py tests/test_ai_council.py tests/conftest.py` — OK
- `python3 -m pytest -q tests/test_ai_council.py` — **312 passed**
- Real `state/costs.jsonl` md5 **identical** before and after the full suite
  (was +6 rows from 3 tests before the fix).
- Confirmed `ai_council.COSTS_FILE` honors `AI_COUNCIL_STATE_DIR`, so the suite
  is now safe to run from `D:\ai-council`.

## Host follow-up (gated, not done here)

1. After approval, set `AI_COUNCIL_LLM_ROUTER=true` in the Desktop env and
   restart the listener. Confirm `/health` shows `llm_router: on`.
2. Telegram smoke:
   - novel phrasing (no slash, no fixed keyword) routes to research/flow;
   - "hej" stays a fast `/chat` with no `task_id`;
   - "usuń wszystkie pliki" stays `/chat`, never execution.
3. Watch `state/costs.jsonl` / `/cost` for router spend after enabling, and tune
   `AI_COUNCIL_LLM_ROUTER_MIN_CONF` / `AI_COUNCIL_LLM_ROUTER_MIN_CHARS` if needed.

## Known follow-up (v2.1, not in this change)

When the router selects `/chat`, the system may then spend a second Grok call to
answer. A future optimization can let the router return an inline chat answer in
the same response when `command=/chat`, avoiding the double call. Out of scope
here to keep the change contained.
