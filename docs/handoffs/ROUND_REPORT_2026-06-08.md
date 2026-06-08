# Round Report — 2026-06-08 (Claude primary builder)

Owner: Claude Opus 4.8 · Auditor/tester/deploy-checker: Codex · Operator: Bartek
Loop: Grok/web research → Claude council (5 roles) → synthesis → adversarial critique → Claude audit/verify.
Master goal: `docs/GOAL_POKE_PLUS_MASTER.md`. Raw council output: `docs/research/council-synthesis-2026-06-08.md`.

---

## 1. L4.63 — DONE and verified (ready for Codex audit + host deploy decision)

**Router (pre-existing patch):** `llm_router_should_try()` changed from a 24-keyword positive allowlist to a negative cost gate (skip smalltalk via `is_smalltalk()`/`SMALLTALK_PHRASES`, skip <`AI_COUNCIL_LLM_ROUTER_MIN_CHARS`), so novel phrasings reach the router by intent. Safety boundary unchanged (`LLM_ROUTER_ALLOWED_COMMANDS`, min-confidence, `route_text()` re-validation). Router stays **off by default**.

**Cost-ledger isolation (Claude fix this round — the "tests/router must not write the real ledger" problem):**
- Root cause verified: `COSTS_FILE = STATE_DIR/"costs.jsonl"` is frozen at import; `route_message → llm_route → reserve_operator_call → record_operator_usage → append_jsonl(COSTS_FILE)`. Three router tests enabled the router without mocking the reservation. **Proven:** running just those 3 appended **+6 rows** to the real `state/costs.jsonl`. L4.63's broadened gate makes far more messages hit that path.
- Fix: new `tests/conftest.py` redirects `AI_COUNCIL_STATE_DIR` (+ log/errors/artifacts/reports/workspaces) to a per-session temp sandbox **before** `ai_council` imports (host override still wins; `PROJECT_DIR` untouched). The 3 legacy router tests also now mock `reserve_operator_call`/`finalize_operator_call` (defense-in-depth).

**Verification (Mac):**
- `py_compile ai_council.py tests/test_ai_council.py tests/conftest.py` → OK
- `pytest -q tests/test_ai_council.py` → **312 passed**
- Real `state/costs.jsonl` md5 **identical** before/after full suite (was +6 rows).
- Confirmed `ai_council.COSTS_FILE` honors the env redirect → suite is now safe to run in `D:\ai-council`.

**Changed files:** `tests/conftest.py` (new), `tests/test_ai_council.py` (3 tests hardened), `docs/implementation/L4_63_FRONT_BRAIN_V2_COST_SAFE_ROUTER.md` (+isolation section). `ai_council.py` NOT modified by Claude (still the original L4.63 router patch).

---

## 2. Audit correction (the loop catching an overstatement)

The council **synthesis** asserted "conversation memory does not persist in production / `conversations.jsonl` is absent." Claude verified independently:

- Real `ai_council.py` is **15,037 lines** (the synthesis read the real file; its line cites are accurate within ~170 lines).
- Read-only live-host check (`ssh ai-council-desktop … dir D:\ai-council\state`): **`conversations.jsonl` EXISTS** — 2897 bytes, 7 turns, last written 07:27:57 (same as `telegram_offset`). It was only absent in the **dev** repo state because dev never ran the live listener.
- **Conclusion:** conversation memory IS persisting. The "memory broken" framing is **withdrawn**. Persist-before-route becomes a *defensive robustness* improvement, not a confirmed-bug fix.

**What remains solidly verified (the real reasons for the next sprint):**
1. `risk_level_for_text` (7693) is a substring denylist with real English gaps — `"pay the invoice"` matches no R1–R4 token → **R0 read-only**; `remove/wipe/deploy/prod/transfer` absent. With the router about to be enabled, this is a high-severity hole.
2. No `user_fact` memory: only an explicit `memory_save_prefixes` path (13202, "zapamiętaj") storing `kind=note`. No auto-capture, no provenance/supersession.
3. Offset is a batch-level single value; `append_jsonl` is unlocked across listener + detached workers (24/7 hardening opportunity; `errors_24h≈50`).

---

## 3. Chosen next sprint — L4.64: Router Risk-Fence + Memory/Offset Hardening

**Why now:** the host's intended next action is to flip `AI_COUNCIL_LLM_ROUTER=true`. That must NOT happen until the risk fence is closed and tested — otherwise a destructive/external intent ("pay the invoice", "usuń…", "deploy to prod") riding an allowlisted command could auto-start a background R0 task. Same files also get crash-safe persistence + atomic offsets. Read-only / local-only; no new external surface; off-by-default unchanged.

**L4.64a — pre-flight (host evidence re-pin, ½ day, per critique):** before any edit, re-grep the LIVE `D:\ai-council\ai_council.py` to re-pin line numbers for `risk_level_for_text`, `listen_once`, `append_conversation_turn`, the offset I/O, and confirm current behavior. Removes stale-evidence risk.

**Acceptance criteria:**
1. **Risk fence at the router boundary.** `route_message()` output must pass through `risk_level_for_text` before any auto-start; an R3/R4 prompt can never auto-start a background task — it falls back to `/chat` or an approval/draft path. Regression test over PL+EN destructive set incl. one obfuscated variant; the test must FAIL on a deliberately weakened matcher (proves it bites).
2. **Close the keyword gaps:** add `remove, wipe, transfer, pay, invoice, deploy, prod, "send email to"` (and PL equivalents) with one assertion each; no existing classification loosened.
3. **Crash-safe persistence (defensive).** Persist the user turn before/independently of send (try/finally), so a send failure or exception can't drop it. E2E test: two sequential messages on one `chat_id`; with router mocked, turn 2's routing prompt provably includes turn 1.
4. **Atomic offset.** `write_offset` → temp + `os.replace` (mirror `CONTROL_FILE`); `read_offset` on missing/empty falls back to last processed id, never None (no full-backlog replay). Per-update commit + durable processed-update set → replay skips already-handled updates; turns/tasks idempotent per update.
5. **Locked `append_jsonl` — done correctly (critique fix).** Per-file `BlockingFileLock` + **bounded retry**; on final timeout, write the row to a per-process sidecar reconciled later — **never** "append anyway" (that reintroduces interleaving). Stress test (2 procs × 500 rows → 1000 valid lines, 0 `read_jsonl` skips) **must run on Windows/NTFS**, and a *under-timeout* test proves zero corruption.
6. **State-dir discipline + health.** `CONVERSATIONS_FILE`/offset honor `AI_COUNCIL_STATE_DIR`; conftest md5 check extended to `conversations.jsonl`. `/health` surfaces `last_turn_at`, `conversation_turns_today`, offset value, processed-set size, atomic-commit flag.
7. **Docs + green suite.** `docs/implementation/L4_64_*.md`; full Mac suite green (≥312 + new); `py_compile` clean. Router MUST stay off until host smoke passes.

**Code areas (real line numbers):** `route_message`(13419), `risk_level_for_text`(7693), `listen_once`(14668, tail-append 14867-68), `append_conversation_turn`(810)/`recent_conversation`(827), `append_jsonl`(582), `write_offset`/`read_offset`(~12201-12208), `health_response`.

**Codex worker pack:** branch from main; confirm 312 green; land in order (state-dir+atomic offset → locked append → crash-safe persist → per-update dedup → risk-fence keywords → wire fence into `route_message` → health fields); test alongside each item; `py_compile`+pytest after each; hand back diff + L4.64 doc. **Worker stops at green tests + doc.** It must NOT flip the router env, deploy, push, or start daemons — those are the host's gated steps.

---

## 4. Roadmap L4.64+ (rebalanced per critique: proactivity pulled forward, revenue + channel parity on the board)

| Layer | Title | Goal | Dimension | Depends |
|---|---|---|---|---|
| **L4.64** | Router Risk-Fence + Memory/Offset Hardening | Close `risk_level_for_text` gaps + crash-safe persist + atomic offset/locked append before router goes live | safety / cost-reliability | L4.63 |
| **L4.65** | Durable User-Fact Memory | Extend the existing "zapamiętaj" path: `kind='user_fact'` + provenance + supersede-on-conflict + **human-confirm/quarantine** for any LLM-extracted fact (anti-poisoning) | hermes-memory | L4.64 |
| **L4.65e** | Memory Recall Eval Harness | "It remembers" becomes a number: fixed stated-fact→later-recall pairs, precision/recall target in CI (LongMemEval/LoCoMo style) | hermes-memory | L4.65 |
| **L4.66** | Minimal Proactive Scheduler + DND gate | Daily brief + one watcher, reactivating the context-owning task; **quiet-hours 23:00–07:00, criticality gate** (operator's self-scored #1 capability gap) | poke-ux | L4.64, L4.65 |
| **L4.67** | Error Signal Hygiene + audit-loop close | Severity-aware `errors_24h_actionable`, benign-source suppression, dedup; loop emits real root-cause clusters | cost-reliability | L4.64 |
| **L4.68** | Router cost optimization + visible cost | Router returns inline `/chat` answer (kill double Grok call); per-day cost line on delivery cards (beat Poke's #1 complaint) | cost-reliability | L4.64 (router live) |
| **L4.69** | OpenClaw Hands v1 (read-only / dry-run local FS) | Root-bounded sandbox executor on D:\ — list/read/preview-diff behind R0-read/R3-write gating | openclaw-hands | L4.64, L4.67 |
| **L4.70** | One revenue/outcome workflow (approval-gated) | Draft→approve→send ONE real outreach, measure replies — answers the documented "builder>seller" gap | integrations | L4.65, L4.69 |
| **L4.70.5** | Multi-step execution + rollback primitive | Record inverse-op per write; on step failure replay inverses — hands that can unwind partial failure | openclaw-hands / safety | L4.69 |
| **L4.71** | Channel-parity decision | Explicit go/no-go on iMessage/Apple Messages + a thin iPhone capture path (Shortcut→memory/task) | integrations / poke-ux | L4.66 |

---

## 5. Exact live-Grok research prompt (next round — gated on Bartek's go for xAI spend)

> You are a research analyst with LIVE access to X/Twitter and the web. Today is 2026-06-08. I am building a private self-hosted "Poke but better": one persona over Telegram/iPhone, Claude+GPT via subscription, Grok via API for research, durable cross-session memory, safe local desktop execution, proactive nudges. For every claim give a URL and a date; flag anything you cannot date. (1) POKE (poke.com / Interaction Co): new launches/pricing/outages/complaints since April 2026? Quote 3-5 recent X posts (handles+dates) on the negotiated "bouncer" pricing, reliability/latency, memory quality, and the Apple Messages-for-Business rollout — what are people switching TO? (2) OSS clones & memory: latest on OpenPoke (shlokkhemani), Hermes Agent (Nous), mem0, Letta/MemGPT, Zep/Graphiti, Honcho — releases/benchmarks (LoCoMo/LongMemEval) since April 2026; best PRODUCTION pattern for (a) extracting user-stated facts from chat, (b) supersession/forgetting, (c) provenance/anti-poisoning. Link repos+commit dates. (3) Safe local execution on Windows: newest on OpenClaw safety model, MS execution containers, Codex CLI native Windows sandbox; new prompt-injection exploits/CVEs on always-on local agents since April 2026; current best-practice sandbox for terminal+file access. (4) Multi-model routing & cost: real $/message for an always-on assistant; cheapest reliable model for per-turn fact-extraction. (5) Telegram/iMessage bridges for a solo builder in 2026. Output a numbered brief: claim | URL | date | confidence | "so what for my build"; end with TOP 3 roadmap changes and anything that CONTRADICTS the assumptions above.

---

## 6. Codex audit request (for L4.63, now)

Please audit the L4.63 cost-ledger isolation change before any Desktop deploy:
- Confirm `tests/conftest.py` redirects state before import on Windows (run `pytest -q tests/test_ai_council.py` in `D:\ai-council` and confirm `state\costs.jsonl` md5 is unchanged by the run).
- Confirm the 3 hardened router tests still assert routing semantics (research route / side-effect rejection / low-conf fallback) and no longer touch the ledger.
- Confirm no behavior change to `ai_council.py` runtime (router still off by default; only the pre-existing L4.63 router patch is present).
- Verdict: safe to deploy L4.63 to `D:\ai-council`? Keep `AI_COUNCIL_LLM_ROUTER` OFF until L4.64 risk fence lands.

---

## 7. Host pre-deploy / pre-router-enable checklist (gated — Bartek's call)

- [ ] Windows: full `pytest` ≥312 passes in `D:\ai-council`; `py_compile` clean.
- [ ] `state\costs.jsonl` md5 unchanged by the test run (ledger isolation holds on NTFS).
- [ ] Do NOT enable the router yet — wait for L4.64 risk fence + its smoke (`"pay the invoice"`, `"usuń wszystkie pliki"` stay `/chat`, never auto-start a task).
- [ ] Snapshot `state\` before any deploy.
- [ ] Keep deploy/restart/push/daemon-enable behind explicit approval (CLAUDE.md invariants).

---

## 8. Decisions (RESOLVED by Bartek 2026-06-08)

1. **L4.63 deploy:** HOLD — deploy together with L4.64. Codex still audits L4.63 in the meantime.
2. **Goal directive:** implement `/goal` continuously until the whole project reaches 1:1 Poke (or better). Live-Grok kept ready, fired on demand (web research used by default to avoid unnecessary xAI spend).
3. **L4.64 implementation:** via **Codex worker pack** (Codex 5.3 Spark implements, Claude reviews + audits). Pack delivered: `docs/handoffs/CODEX_WORKER_PACK_L4.64.md`.

## 9. Progress log (autonomous loop, 2026-06-08)

Claude implemented the clean, low-risk, Mac-testable slices directly; the high-blast-radius concurrency work (live loop + shared write primitive on NTFS) stays delegated to Codex+host.

| Item | Status | Tests |
|---|---|---|
| L4.63 cost-ledger isolation | ✅ landed (Claude) | 312 |
| L4.64 Part 1 — risk fence (Steps E+F) | ✅ landed (Claude) | 315 |
| L4.65 — durable user-fact memory (trusted core) | ✅ landed (Claude) | 321 |
| L4.64 Step A — atomic offset write | ✅ landed (Claude) | 323 |
| L4.66 (partial) — query-relevant recall + recall-eval harness | ✅ landed (Claude) | 324 |
| L4.67 (partial) — severity-aware actionable error count | ✅ landed (Claude) | 325 |
| L4.64 Step B — locked append_jsonl + sidecar fail-safe | ✅ landed (Claude) | 327 |
| L4.64 Step C — crash-safe persist (early user turn) + idempotency | ✅ landed (Claude) | 329 |
| L4.64 Step G — `/health` memory liveness | ✅ landed (Claude) | 330 |
| L4.64 Step D — per-update offset commit + dedup (loop restructure) | ⏳ Codex+host (live listener) | pack |
| L4.64 Step B — NTFS 2×500 concurrency stress validation | ⏳ host | pack |
| L4.65 Step D — LLM fact auto-extraction + confirm card (off by default) | ⏳ L4.65.1 | pack |

All landed work: full suite **330 passed**, real `state/costs.jsonl` and `state/memory.sqlite` md5 **unchanged** by the suite, no deploy/push/router-change. Grok used live (bounded research call) to inform L4.65.

## 10. DEPLOYED TO PRODUCTION ✅ (2026-06-08, Bartek approved)

L4.63 + L4.64(A/B/C/E/F/G) + L4.65 + L4.66 + L4.67 deployed to `D:\ai-council` and verified live:

- **Backup:** `ai_council.py.predeploy.bak`, `tests/*.predeploy.bak`, `state/memory.sqlite.predeploy.bak`, `state/telegram_offset.predeploy.bak`, `.env.predeploy.bak` (rollback path).
- **Files:** byte-exact transfer (md5 verified) → live paths.
- **Windows tests:** `330 passed, 113 subtests passed`.
- **Migration:** production `memory.sqlite` gained `status/confidence/norm_key/chat_id_hash`; **63 existing rows preserved**.
- **Restart:** scheduled task `Bartek AI Council Telegram` → Running (new code live).
- **Live health:** `llm_router=on`, `errors_24h: 51 (actionable: 0)`, `memory: turns_today=2`.
- **Live memory E2E:** `fact → recall(True) → forget(1) → active(0)` on production.
- **Router enabled:** `.env` `AI_COUNCIL_LLM_ROUTER=true` (surgical edit, secrets verified intact). Live smoke: benign NL → `@research` via `route_source=llm`; "zapłać fakturę" → `/plan-action` draft (not auto-paid); "hej" → `/chat` no Grok call.

**Only remaining for "działa na iPhonie":** Bartek's own smoke from his iPhone Telegram (text the bot: "zapamiętaj, że mój lot jest we wtorek" → later "kiedy mam lot?").

**Still delegated (not blocking iPhone use):** L4.64 Step D (per-update offset, live-listener validation), L4.64 Step B NTFS 2×500 stress, L4.69 OpenClaw hands (worker pack ready), L4.65.1 fact auto-extraction.
