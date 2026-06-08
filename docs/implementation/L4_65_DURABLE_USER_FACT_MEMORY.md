# L4.65 — Durable User-Fact Memory (Hermes core)

Date: 2026-06-08 · Owner: Claude Opus 4.8 (primary builder)
Status: **Trusted-path core LANDED + tested by Claude.** LLM auto-extraction wiring (off-by-default) deferred to L4.65.1.
Research input: bounded live-Grok call (xAI API) on memory supersession + anti-poisoning patterns — informed the deterministic `norm_key`, human-source-wins supersession, and quarantine design.

## Why (the iPhone goal)

This is the feature that makes the assistant feel like Poke/Hermes from the phone: **"text it a fact, it remembers and uses it later."** Before, the only user-fact path stored `kind="note"` with no provenance, no conflict handling, and no trust model. L4.65 makes user facts durable, self-superseding, and safely recalled.

## Change

New columns on `memory_entries` (additive migration, backward-compatible): `status` (`active|superseded|quarantine|rejected`), `confidence`, `norm_key`, `chat_id_hash`. New API:

- `derive_user_fact_norm_key(value)` — deterministic subject head (first salient token, synonym-mapped, no LLM).
- `user_fact_save(value, *, source, chat_id_hash, confidence, status)` — stores `kind="user_fact"`; an **active human-sourced** fact supersedes prior active facts with the same `norm_key` (latest wins). Values are `redact_secrets`-cleaned.
- `active_user_facts(limit)` — active facts with `confidence >= AI_COUNCIL_USER_FACT_MIN_CONF` (default 0.75).
- `user_fact_forget(target)` — supersede by entry_id / norm_key / value match (history preserved, never hard-deleted).
- `user_fact_promote(entry_id)` / `user_fact_reject(entry_id)` — confirm/reject a quarantined LLM fact (promote → active, confidence 1.0).

Wiring:
- "zapamiętaj / zapisz do pamięci / remember" → `/memory fact <body>` → `user_fact_save(... source="telegram_user")` (trusted, active). Leading connector ("że") stripped.
- `memory_context_for_prompt` prepends **"Co wiem o Tobie:"** with active facts and excludes non-active `user_fact` rows from generic memory — so a superseded/quarantined fact is never recalled. Recall is already injected into chat/research prompts (callers at 498, 13744, 13797, 14143).
- `/memory facts` lists active facts; `/memory forget <x>` supersedes.

## Anti-poisoning (anticipates L4.65.1)

LLM-extracted facts must be saved with `status="quarantine"` and are **never** auto-trusted: excluded from `active_user_facts`/recall until `user_fact_promote` (explicit human confirm). The actual extraction call + Telegram confirm-card (✅/❌ → promote/reject) is L4.65.1, **off by default** (`AI_COUNCIL_FACT_EXTRACTION` unset). The storage/trust API is already in place and tested.

## Anchors (repo)
`init_memory_db` (~7328, schema+migration), user-fact block after `memory_response` (~7541), `memory_context_for_prompt` (~7485), `memory_response` (`facts`/`forget`/`fact`), "zapamiętaj" route (~13232).

## Tests (tests/test_ai_council.py::MemoryUserFactTests)
save+recall, supersession latest-wins, forget, quarantine-until-promote, zapamiętaj→fact persistence (+ connector strip), backward-compatible migration. Each isolates `MEMORY_DB` to a temp file.

## Verification
- `py_compile ai_council.py tests/test_ai_council.py tests/conftest.py` — OK
- `pytest -q tests/test_ai_council.py` — **321 passed** (was 315)
- `state/costs.jsonl` AND `state/memory.sqlite` md5 **unchanged** by the suite.

## Safety invariants
- No external write/exec/deploy/router change. Secrets redacted before storage. LLM extraction off by default + quarantined. Supersede (not delete) preserves an audit trail.

## Host iPhone smoke (gated)
From Bartek's iPhone (Telegram): "zapamiętaj, że mój lot jest we wtorek" → later "kiedy mam lot?" uses it; "zapamiętaj, że lot jest w czwartek" → "kiedy mam lot?" returns Thursday; `/memory facts` lists it; `/memory forget lot` clears it. Migration runs once on `D:\ai-council\state\memory.sqlite` (snapshot first).

## L4.66 (partial) — query-relevant recall + eval harness (LANDED with L4.65)

- `active_user_facts(limit, query="")` now ranks active facts by token overlap with the query when facts exceed `limit`, padding with the most recent — so recall surfaces the RIGHT fact for the question while keeping core context. `memory_context_for_prompt` passes the prompt as the query.
- **Recall-eval harness** (`test_recall_eval_surfaces_right_fact_among_many`): seeds 8 distinct facts, queries each, asserts recall ≥ 0.75. Turns "it remembers" into a measured number (addresses the council critique). Suite: **324 passed**.

## Known limitation (→ L4.66 full)
`norm_key` is a first-salient-token heuristic; multi-subject facts may not supersede ideally. The full L4.66 adds memory decay/forgetting (recency×relevance×importance) on top of the eval harness already in place.
