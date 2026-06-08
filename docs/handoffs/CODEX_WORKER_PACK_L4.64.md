# Codex Worker Pack — L4.64 Router Risk-Fence + Memory/Offset Hardening

Prepared by: Claude Opus 4.8 (primary builder) · For: Codex 5.3 Spark worker · Audit: host Codex · Date: 2026-06-08
Plan source: `docs/handoffs/ROUND_REPORT_2026-06-08.md` · Council record: `docs/research/council-synthesis-2026-06-08.md`

You are the **implementation worker**. Implement exactly the scope below, with a test for every change, against the **repo** (source of truth). Do not exceed scope. Hand back a diff + an L4.64 implementation doc. Host Codex audits and deploys; **you do not deploy, push, restart, enable the router, or touch `.env`/secrets.**

---

## 0. Source of truth & line-number note

- Implement against the **Mac repo** `ai_council.py` (**15,037 lines**, contains the L4.63 dirty patch). This is ahead of the live host `D:\ai-council\ai_council.py` (**13,719 lines**, still L4.62). Deploy later syncs repo→host. Use the **repo** anchors below; if a line moved, re-grep the function name (anchors are by `def`, stable).
- The L4.63 patch (router cost gate + `tests/conftest.py` cost-ledger isolation) is already in the worktree. **Keep it.** Run the suite first to confirm the **312-passing** baseline before you change anything.

## STATUS UPDATE (2026-06-08): Steps E, F, A, B, C, G are ALREADY DONE by Claude

Landed + tested (suite **330 passed**, ledger unchanged) — **do NOT redo E, F, A, B, C, G.** See `docs/implementation/L4_64_ROUTER_RISK_FENCE_AND_MEMORY_HARDENING.md`.

**Your job is now narrow:**
1. **Step D** — per-update offset commit + durable processed-update dedup in `listen_once` (no backlog replay, no dup turns/tasks). This restructures the live polling loop's offset/`continue` flow, so it MUST be validated against the real Telegram listener (not just unit tests) — that's why it's delegated.
2. **NTFS stress-validate Step B** (already implemented): run 2 processes × 500 `append_jsonl` rows on the real Windows box → assert 1000 valid `read_jsonl` rows, 0 skips; force a lock timeout → row lands in a `*.sidecar-*.jsonl` and is reconciled on the next append (never interleaved). The implementation + fail-safe are done; you are CONFIRMING them under real NTFS concurrency.

Branch from the current worktree (it already contains L4.63 + L4.64 E/F/A/B/C/G + L4.65/66/67).

## 1. Scope (and why each item matters)

This sprint makes it **safe to enable the LLM router** and hardens the 24/7 substrate. All read-only/local; no new external surface; router stays **off by default**.

1. **Close `risk_level_for_text` keyword gaps.** This function is the substring risk classifier used by **every** gate: draft creation (`2823`), action risk (`7760`), target risk (`7769`), prompt risk (`7874`), provider write (`11101`). Verified hole: `"pay the invoice"` matches no R1–R4 token → classified **R0 (read-only)**. Missing tokens: `remove, wipe, transfer, pay, invoice, deploy, prod, "send email to"` (+ PL). Closing these strengthens the whole safety model at once.
2. **Router-boundary risk fence (defense-in-depth).** When `llm_route` selects an allowlisted command, an R3/R4-classified prompt must not ride it into an auto-started background task. Force fallback to `/chat` in that case.
3. **Crash-safe conversation persistence (defensive).** Turns are appended at the listener tail (`14867-68`) after send; a send/exception before the tail can drop the user turn. Persist the user turn via try/finally so it cannot be skipped. (Note: persistence is NOT broken in production — `conversations.jsonl` exists on the host with live turns — this is robustness, not a bugfix.)
4. **Atomic offset + safe replay.** `write_offset` (`12208`) is non-atomic; `read_offset` (`12201`) returning None risks full-backlog replay. Make writes atomic and reads fail-safe; dedup already-processed updates.
5. **Locked `append_jsonl` (`582`) done correctly.** Serialize cross-process appends; on lock-timeout use a per-process **sidecar** file reconciled later — never interleave bytes (do NOT "append anyway").
6. **Health visibility + state-dir discipline + docs.**

## 2. Verified anchors (repo)

| Symbol | Line | Role |
|---|---|---|
| `SIDE_EFFECT_COMMANDS` | 134 | `{"/write","/append","/patch","/propose"}` |
| `append_jsonl` | 582 | unlocked cross-process append → add per-file lock |
| `BlockingFileLock` | 658 | reuse this primitive |
| `append_conversation_turn` / `recent_conversation` | 810 / 827 | turn persistence + lookup |
| `CONVERSATIONS_FILE` / `OFFSET_FILE` | 71 / 55 | both under `STATE_DIR` already |
| `build_response` auto-start | ~3984-4005 | `route_needs_task`→`route_should_background`→`start_background_job` |
| `save_control_state` atomic template | 4706-4712 | `tmp = X.with_name(f"{name}.tmp-{pid}-{tid}")` then `os.replace(tmp, X)` — copy this for `write_offset` |
| `risk_level_for_text` | 7693 | the substring classifier to fix |
| `read_offset` / `write_offset` | 12201 / 12208 | offset I/O |
| `llm_route` (sets `route_source="llm"`) | 12722 (return ~12794) | wire the fence here |
| `route_message` | 13419 | router entry |
| `listen_once` (tail append) | 14668 (14867-68) | reorder persistence |

## 3. Implementation steps (dependency order — test alongside each)

**Step A — atomic offset + safe read.**
- `write_offset`: write to `OFFSET_FILE.with_name(f"{OFFSET_FILE.name}.tmp-{os.getpid()}-{threading.get_ident()}")` then `os.replace(tmp, OFFSET_FILE)` (mirror 4710-4712).
- `read_offset`: on missing/empty/corrupt, return the last durably-recorded processed id (persist a `last_processed_update_id`), never None→backlog.
- Test: write then truncate the tmp mid-write (simulate) → `read_offset` returns a valid int, no exception; offset file never half-written.

**Step B — locked `append_jsonl` + sidecar fail-safe.**
- Wrap the append in a **per-file** `BlockingFileLock` (lock path = `<file>.lock`), short timeout (`AI_COUNCIL_APPEND_LOCK_TIMEOUT`, default 5s). On `TimeoutError`, append the single JSON line to `<file>.sidecar-<pid>.jsonl` and record a warning; add a `reconcile_sidecars(path)` that merges sidecar lines under the lock at next successful acquire / listener start.
- Tests: (1) 2 processes × 500 rows → `read_jsonl` returns 1000 valid rows, 0 skips; (2) force a lock timeout → row lands in a sidecar (not interleaved) and `reconcile_sidecars` merges it; assert zero malformed lines under timeout.

**Step C — crash-safe persistence in `listen_once`.**
- Persist the **user** turn right after `route_message` returns (before `build_response`/send), wrapped so an exception in build/send cannot skip it; keep the assistant-turn append where it is. Guard idempotency by `update_id` so a replay does not double-append.
- Test: drive the per-update handler for 2 messages on one `chat_id` with the router mocked; assert turn 1 is in `conversations.jsonl` before turn 2 is routed, and turn 2's routing prompt (via `recent_conversation`) contains turn 1's text.

**Step D — per-update offset commit + replay dedup.**
- Commit the offset per fully-handled update; consult a durable processed-update set at the top of the per-update loop; skip routing/persist/nudges for already-handled updates; task creation resolves to the existing `task_id` on replay (extend beyond the 90s idempotency window).
- Test: simulate a mid-batch crash + replay → no duplicate turns, no duplicate task, no second nudge.

**Step E — close `risk_level_for_text` gaps.**
- Add to the **R4** set: `remove`, `wipe`, `transfer`, `pay`, `invoice`, `deploy`, `prod`, `send email to`, `wyślij maila`, `przelej`, `zapłać`, `faktura`, `wdroż`, `wdróż`, `produkcja`. (Keep existing tokens; loosen nothing.)
- Tests (one assert each): `"pay the invoice"`, `"remove all data"`, `"wipe the disk"`, `"deploy to prod"`, `"transfer money"`, `"wyślij maila do klienta"`, `"przelej 1000 zł"` each classify **R4** (or at least ≥R3); plus a guard test that existing R0 phrases (`"co słychać"`, `"zrób research o Poke"`) still classify R0.

**Step F — router-boundary fence in `llm_route`.**
- Before returning the validated route, compute `risk, _ = risk_level_for_text(f"{command} {prompt}")`; if `risk` in `{"R3","R4"}`, return None (→ `/chat` fallback) instead of an auto-startable route. Add a `route_reason` note.
- Test: with the router enabled+mocked to return e.g. `@research` + prompt `"pay the invoice"` / `"usuń wszystkie pliki"`, `route_message` must NOT return a command that auto-starts a task — it falls back to `/chat`. The test must **fail** if Step E's keywords are reverted (proves the fence bites).

**Step G — health + docs.**
- `/health` (find `health_response`/`/health` builder): add `last_turn_at`, `conversation_turns_today`, `telegram_offset`, `processed_updates`, `offset_atomic=true`.
- Extend `tests/conftest.py` md5-guard to also assert `conversations.jsonl` and `telegram_offset` under the live `STATE_DIR` are untouched by the suite.
- Write `docs/implementation/L4_64_ROUTER_RISK_FENCE_AND_MEMORY_HARDENING.md` (problem, change, anchors, safety invariants, verification, host follow-up). State: router stays OFF until host smoke passes.

## 4. Safety boundaries (worker MUST NOT)

- No `.env`/secrets/auth/billing/DNS edits; no external write/provider calls; no shell-exec features.
- No deploy/push/restart/daemon start; **do not** flip `AI_COUNCIL_LLM_ROUTER`.
- No change that loosens any existing risk classification or removes a gate.
- Router remains **off by default**; `SIDE_EFFECT_COMMANDS` behaviour unchanged.
- Keep the L4.63 conftest/ledger isolation intact.

## 5. Acceptance criteria

- Full Mac suite green: **≥312 + all new tests**; `python3 -m py_compile ai_council.py tests/test_ai_council.py tests/conftest.py` clean.
- Real `state/costs.jsonl`, `conversations.jsonl`, `telegram_offset` md5 unchanged by the suite.
- The fence test fails when Step E keywords are reverted (proves enforcement).
- Concurrency stress test passes (1000 rows, 0 skips) and the under-timeout test shows zero corruption.
- Diff scoped to: `ai_council.py`, `tests/test_ai_council.py`, `tests/conftest.py`, new `docs/implementation/L4_64_*.md`. No other files.

## 6. Verification commands

```bash
python3 -m py_compile ai_council.py tests/test_ai_council.py tests/conftest.py
python3 -m pytest -q tests/test_ai_council.py
python3 -m pytest -q tests/test_ai_council.py -k "risk or fence or offset or append or conversation or replay"
```

## 7. Host review checklist (Codex, before deploy — gated)

- [ ] Diff scoped; no secrets in `git status` (the L4.49 secret guard).
- [ ] Windows: full `pytest` ≥312+new green in `D:\ai-council`; `py_compile` clean.
- [ ] **NTFS** concurrency stress (2×500) on the real box → 1000 valid lines, 0 skips; sidecar reconcile works.
- [ ] `state\costs.jsonl` / `conversations.jsonl` / `telegram_offset` md5 unchanged by the test run.
- [ ] Risk-fence smoke (router still off): unit-level proof that `"pay the invoice"`, `"usuń wszystkie pliki"` classify ≥R3 and don't auto-background.
- [ ] Kill listener mid-batch + restart → no backlog replay, no dup turns/tasks.
- [ ] Snapshot `state\` before deploy. Keep `AI_COUNCIL_LLM_ROUTER` OFF after deploy.

## 8. What Claude reviews on worker return

Router fence correctness (no R3/R4 auto-background), no loosened classifications, sidecar fail-safe truly non-interleaving, offset atomicity + replay idempotency, persistence ordering, test quality (fence test must bite), docs. Then Claude issues the host-audit request and the router-enablement smoke matrix.
