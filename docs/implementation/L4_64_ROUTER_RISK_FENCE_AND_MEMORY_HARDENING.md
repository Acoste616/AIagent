# L4.64 — Router Risk-Fence + Memory/Offset Hardening

Date: 2026-06-08 · Owner: Claude Opus 4.8 (primary builder)
Status: **Part 1 (risk fence) LANDED by Claude; Part 2 (concurrency/persistence hardening) delegated to Codex worker** (`docs/handoffs/CODEX_WORKER_PACK_L4.64.md`).

## Why

The host's next intended action is to enable the LLM router (`AI_COUNCIL_LLM_ROUTER=true`). With the router on, free-form text reaches `llm_route`, which can select an allowlisted read/think command. The only thing stopping a destructive/external intent from riding that command into an auto-started background task is `risk_level_for_text()` — a substring classifier that had verified English gaps. This layer closes those gaps and adds a fence at the router boundary, so the router can be turned on safely.

## Part 1 — LANDED (Claude, this round)

### Change 1: `risk_level_for_text` (ai_council.py:7693) — close keyword gaps
This classifier feeds **every** risk gate (draft creation 2823, action risk 7760, target risk 7769, prompt risk 7874, provider write 11101), so closing its holes hardens the whole safety model at once.

Verified hole before: `"pay the invoice"` matched no R1–R4 token → classified **R0 (read-only)**. Added to the **R4** set (no existing classification loosened):
`send email to, wyślij maila, remove, wipe, erase, transfer money, wire transfer, send money, przelej, pay the, pay invoice, make payment, zapłać, zaplac, faktur, deploy, wdroż, wdróż, do produkcji, to prod, on prod`.
(Deliberately avoided bare-substring false positives like `pay`/`prod`/`invoice` — used phrase forms so e.g. "product"/"display" don't over-gate.)

### Change 2: `llm_route` (ai_council.py:~12787) — router risk fence
Before returning the validated route, the router now classifies `command + prompt + message`; if **R3/R4**, it returns `None` → `/chat` fallback. So an allowlisted command (e.g. `@research`) carrying a destructive prompt (e.g. "pay the invoice") can never auto-start a task. The allowlist (no write/execute), min-confidence, and `route_text()` re-validation are unchanged; this is defense-in-depth on top.

### Tests (tests/test_ai_council.py)
- `test_risk_fence_classifies_destructive_phrases` — 9 PL+EN destructive phrases now classify R3/R4.
- `test_risk_fence_keeps_benign_phrases_read_only` — benign phrases stay R0 (no over-gating regression).
- `test_llm_router_fence_blocks_destructive_prompt_to_chat` — benign message reaches the router, router returns a destructive prompt, fence falls back to `/chat` (`route_source=fallback`).

### Verification
- `py_compile ai_council.py tests/test_ai_council.py tests/conftest.py` — OK
- `pytest -q tests/test_ai_council.py` — **315 passed** (was 312)
- Real `state/costs.jsonl` md5 **unchanged** by the suite (L4.63 isolation holds).
- **Fence is load-bearing:** with the pre-L4.64 keyword set, "pay the invoice" → R0 (fence would not bite); with the change → R4 (fence bites). Proven by a revert check.

### Safety invariants (unchanged)
- Router still **off by default**; no external write/exec/deploy/daemon. No classification loosened. `SIDE_EFFECT_COMMANDS` behaviour unchanged. No `ai_council.py` change outside these two functions.

## Part 2 — hardening (mostly LANDED by Claude, 2026-06-08; suite 330 passed)

| Step | What | Status |
|---|---|---|
| **A** | atomic `write_offset` (temp+`os.replace`); safe `read_offset` | ✅ landed (`OffsetAtomicityTests`) |
| **B** | per-file locked `append_jsonl` + sidecar fail-safe (never interleave/drop; `_reconcile_append_sidecars`) | ✅ landed (`AppendJsonlLockTests`) — **NTFS 2×500 stress still to run on host** |
| **C** | crash-safe conversation persistence: user turn persisted **before** build/send in `listen_once`, idempotent by `update_id` (`append_conversation_turn(..., update_id=)`) | ✅ landed (`ConversationPersistenceTests`) |
| **G** | `/health` memory liveness (`conversation_liveness()` → `turns_today`/`last_turn_at`, line 8 of `/front`) | ✅ landed |
| **D** | per-update offset commit + durable processed-update dedup (loop restructure) | ⏳ host/Codex — needs live-listener validation |

Step B's locking logic is unit-tested via a forced-timeout→sidecar→reconcile test; the **real NTFS concurrency stress (2 procs × 500 rows → 1000 valid lines, 0 skips) must still run on the Windows box** before trusting it 24/7. Step D restructures the live polling loop's offset/`continue` flow and should be validated against the real Telegram listener, so it stays delegated. See `docs/handoffs/CODEX_WORKER_PACK_L4.64.md`.

## Host follow-up (gated)
- Deploy L4.63 + L4.64 together after host audit + approval.
- Keep `AI_COUNCIL_LLM_ROUTER` OFF until Part 2 lands AND the smoke passes: send "usuń wszystkie pliki" / a payment phrase → stays `/chat`, never auto-starts a task.
