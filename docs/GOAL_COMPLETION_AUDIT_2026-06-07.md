# Goal Status Audit

Date: 2026-06-07
Updated: 2026-06-07 20:30 Europe/Warsaw

Goal:

Build a working Poke-like/OpenClaw-like AI Council on Windows Desktop:

1. Research Poke through Grok/X.
2. Ask Claude for long dynamic-workflow analysis.
3. Ask Claude to run an AI Council tournament.
4. Audit conclusions independently.
5. Implement verified changes in `D:\ai-council`.
6. Verify through Telegram/status/tests.

## Evidence Matrix

| Requirement | Evidence | Status |
|---|---|---|
| Grok/X Poke research | `docs/research/grok-x-poke-research-2026-06-06.md`, raw JSON, copied to `D:\ai-council\docs\research` | Proven |
| Claude long analysis | `docs/research/claude-opus48-poke-research-full-2026-06-06.md`, copied to desktop docs | Proven |
| Claude tournament | `docs/research/claude-opus48-tournament-scorecard-2026-06-06.md`, copied to desktop docs | Proven |
| Independent target synthesis | `docs/POKE_CLONE_TARGET.md` | Proven |
| Windows deployment | L4.46 copied to `D:\ai-council\ai_council.py`, `D:\ai-council\tests\test_ai_council.py`, and `D:\ai-council\docs\implementation\L4_46_MOBILE_ACTIVATION_ADVISOR.md`; Telegram listener restarted through `windows-deploy` stop/start scripts at 2026-06-07 20:29 | Proven |
| Telegram service running | Scheduled task `Bartek AI Council Telegram` state `Running`; one Python `serve --send` process | Proven |
| Operators configured | Desktop health: Codex OK, Claude OK, Claude Flow Opus 4.8 OK, Grok OK | Proven |
| Long work non-blocking | Background jobs, task IDs, artifacts, delivery cards implemented and covered by tests | Proven |
| Safe execution | Risk Officer R0-R4, approval, execute, verify, rollback implemented and covered by tests | Proven |
| Media/iPhone path | Telegram media capture, xAI STT, Grok vision, media-to-intent, optional Shortcuts ingress implemented | Proven |
| Final delivery UX | L3.5 delivery cards with Status/Details/Facts/Next, no Cancel on completed tasks | Proven |
| Status verification | Desktop `server-access-status.ps1`, `/health`, `/selftest` work | Proven |
| Test verification | L4.46: Mac py_compile, agent/proactive/shortcut target tests `26/26 OK`, full `237/237 OK`; Windows Desktop py_compile, target tests `26 passed, 211 deselected`, full `237 passed, 111 subtests passed` | Proven |
| Telegram outbound verification | Real Telegram `sendMessage` from desktop returned `telegram_send=True` | Proven |
| Telegram fresh inbound verification | Audit log: `update_id=437154823`, `command=/selftest`, `status=responded`; service log: `telegram_sendMessage=ok`, `offset_saved=437154824` | Proven |
| GitHub push to `Acoste616/AIagent` | L4.46 functional commit ready/pushed in this deployment set: `6b6d1d0 Add mobile activation advisor`; L4.45 functional commit `1e33995` remains present | Proven |
| Claude review | Claude Code reviewed L4.46; findings on RUN fallback comments and Shortcuts status error handling were applied before deployment. Safety confirmed: no token generation, no env writes, no daemon start. | Proven |

## Current Desktop State

- Project: `D:\ai-council`
- Scheduled task: `Bartek AI Council Telegram`
- Process: scheduled task restarted successfully; state `Running`, `LastTaskResult=267009`, `LastRunTime=07.06.2026 20:29:45`.
- Health: env OK, Codex OK, Claude OK, Claude Flow Opus 4.8 OK, Grok OK, L4.46 `agent_mobile_advisor`, L4.45 `shortcuts_service_pack`, L4.44 `memory_front=on`, L4.43 `loop_cadence=on`, L4.42 `default_front=on`, L4.41 `provider_read_before_write=on`, L4.40 `drive_document_executor=gated`, L4.39 `host_contract=on`, L4.38 `provider_dedupe=on`, L4.37 `action_cards=on`, L4.36 `poke_gap=on`, L4.35 `safe_autostart=on`, provider executors still gated until provider-specific env/auth are enabled.
- Selftest: version now starts with `L4.46 Mobile Activation Advisor + L4.45 iPhone Shortcuts Service Pack`; docs OK, operators OK, Telegram configured, Shortcuts state `token_missing_not_started`.
- Loops smoke: `/loops` returns `Autonomous loops L4.43`; `error_audit_twice_daily` next windows `2026-06-07 21:00 +0200`, `2026-06-08 09:00 +0200`; `feature_evolution_loop` next windows `2026-06-07 22:15 +0200`, `2026-06-08 10:15 +0200`.
- Agent smoke: `/agent` returns `Agent Inbox L4.46`; top priority is `[iphone_setup/101]`, `NEXT: /shortcuts`, and `RUN` points only to a separate safe improvement action, not Shortcuts startup.
- Shortcuts smoke: `/shortcuts` returns `iPhone Shortcuts L4.45`, Windows paths for `start/status/stop-ai-council-shortcuts.ps1`, `service: not_started_by_default`, and `token: missing`; `status-ai-council-shortcuts.ps1` reports `State: Stopped`.
- Front smoke: the exact complaint `Ani nie odpowiada on jak poke...` routes to `/poke-gap` and returns a short `Poke Gap L4.44` response that says the goal remains active and L4.45 is the current iPhone service-pack layer.
- Memory-front smoke: with front LLM disabled for the process, `a teraz krócej` after prior local turn `zrób research o Poke` returns `OSTATNI WĄTEK: Ty: zrób research o Poke` and does not start a blank status response.

## Completion Decision

The Windows Desktop baseline is proven: research, Claude planning, tournament, audited implementation, desktop deployment, Telegram live inbound/outbound, status, and tests are all evidenced.

The broader user goal is not complete. Poke parity requires the assistant to feel like one capable personal operator with live integrations, recipes, proactive follow-up, iPhone capture, and safe execution. Current status is a working baseline plus partial Poke-like layers, not final parity.

Next required layers:

1. Configure `AI_COUNCIL_SHORTCUT_TOKEN` on Windows only after approval, then start `start-ai-council-shortcuts.ps1` manually and connect iOS Shortcuts.
2. Private iMessage/Apple Messages bridge only after the Telegram and iPhone Shortcuts core is stable.
3. Deeper source-backed integrations and proactive topic ownership.
4. Broader execution verifier coverage beyond workspace write/append/patch and optional token-level streaming if it proves useful.
5. Cleanup of long runtime version strings into one source of truth.

Completed layers in the current implementation state:

- L4.14 Google OAuth read-sync for Gmail/Calendar/Drive.
- L4.15 Poke Action Planner: one natural message -> planned task/preview/risk/cost/start path without slash.
- L4.16 Live Recipes: Action Planner selects deterministic recipes for research/Gmail/Calendar/Drive/error-audit/evolution and exposes `/loops`.
- L4.17 Follow-up Runner: completed recipes create follow-up proposals; approved safe follow-ups can start the next task, while R3/R4 stay checkpoint-only.
- L4.18 Budget Guard/Kill Switch: `/control` can pause/kill model calls, scheduled recipes, and proactive scan; daily total and per-operator limits guard expensive calls.
- L4.19 Verifier Evidence: `/verify` persists `verified` or `verify_failed` evidence with concrete checks; `/rollback` works after `executed`, `verified`, and `verify_failed`.
- L4.20 Progress UX: background jobs now show START, RUNNING, and final delivery-card stages in Telegram instead of looking silent while work is running.
- L4.21 Unified Front Orchestrator: direct operator routes now return one host-style Telegram response while raw Codex/Claude/Grok output stays available in artifacts/reports.
- L4.22 Project Memory Spine: completed artifacts write source-backed project-memory rows for decision/facts/next; `/project-memory` exposes recent/search/context/rebuild; operator prompts auto-recall project memory with sources.
- L4.23 Cost Ledger Reservation: model calls reserve cost/call budget before execution, `reserved -> final` rows collapse to one logical usage, and the LLM router no longer burns Grok on ordinary chat by default.
- L4.24 Poke Front Reliability: `/front` reports Telegram/audit/model front state, short chat is local-first, and Grok chat is gated so diagnostics do not burn research budget.
- L4.25 Rich Progress Streaming: long background tasks write durable progress events, expose `/progress <task_id>`, include progress timeline in `/status`, send heartbeat for long work, and avoid extra Telegram spam on short jobs.
- L4.26 Agent Inbox: `/agent` aggregates tasks, approvals, follow-ups, improvements, errors, and nudges into one prioritized next action; `/agent run` starts only safe local next steps and keeps R3/R4 behind explicit approval.
- L4.27 iPhone Primary Capture: `/shortcuts` exposes private iPhone ingress status, Share Sheet URLs route to `research_brief`, read-only Shortcut control actions open `/agent/status/progress/details/facts/next`, mutating `approve/deny/cancel` is blocked back to Telegram approval, and recent Shortcut inputs appear in `/agent`.
- L4.28 Integration Action Drafts: `/connector draft gmail|calendar|drive|github <intent>` creates local `integration_draft` pending actions; Action Planner converts integration side-effect requests into structured drafts; approval records a checkpoint only and `/execute` remains blocked for R3/R4.
- L4.29 Integration Execution Packs: approved `integration_draft` actions now support `/execute <id>` to create local JSON/Markdown outbox packs under `artifacts/integration-outbox/<id>` and `/verify <id>` checks pack existence, action/connector match, `external_write=false`, and safe `manual_outbox_pack` provider action.
- L4.30 Provider Adapter Manifests: `/provider plan <id>` creates per-connector provider manifests for Gmail/Calendar/Drive/GitHub with operation, endpoint, scopes, auth readiness, missing-field blockers, local verification, and an explicit `disabled_l4_30_manifest_only` write gate.
- L4.31 Provider Write Gate: `/provider request <id>` creates a separate `provider_write_request` pending action after verified manifests; `/approve <request_id>` records the checkpoint; `/provider execute <request_id> <confirm>` writes a local dry-run/blocker artifact with `external_write_performed=false`; `/provider verify <request_id>` verifies the dry-run evidence.
- L4.32 GitHub Issue Executor v0: `/provider execute <request_id> <confirm>` can create a GitHub issue only for `github.issues.create`, only after request approval, only with `AI_COUNCIL_PROVIDER_WRITE_ENABLED=true`, `AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED=true`, and `GITHUB_TOKEN/GH_TOKEN`; `/provider verify <request_id>` verifies provider result artifacts with URL/id/number evidence. Other providers remain dry-run/blocker only.
- L4.33 Gmail Draft Executor v0: `/provider execute <request_id> <confirm>` can create a Gmail draft only for `gmail.users.drafts.create`, only after request approval, only with `AI_COUNCIL_PROVIDER_WRITE_ENABLED=true`, `AI_COUNCIL_GMAIL_DRAFT_WRITE_ENABLED=true`, and Google OAuth; it creates a draft only, never sends email.
- L4.34 Calendar Event Executor v0: `/provider execute <request_id> <confirm>` can create a Calendar event only for `calendar.events.insert`, only after request approval, only with `AI_COUNCIL_PROVIDER_WRITE_ENABLED=true`, `AI_COUNCIL_CALENDAR_EVENT_WRITE_ENABLED=true`, and Google OAuth; it uses `sendUpdates=none`.
- L4.35 Poke Safe Autostart + Reminder/Calendar Intent: Action Planner auto-starts safe R0 research/recipe/flow/council routes instead of requiring `start task-...`; reminder/calendar phrases create Calendar integration drafts behind approval; `/connector` auto-start is scoped to read-only subcommands; `respond` CLI dry-runs full response generation for debugging.
- L4.36 Poke Host Gap: feedback such as `nie odpowiadasz jak Poke`, `nie ma takich możliwości`, `gdzie ten cel`, or `poke parity` routes to `/poke-gap` instead of the long `/goal` dump; the response is bounded, includes the user's phrasing, admits parity is not complete, and creates one idempotent P0 improvement backlog item.
- L4.37 Poke Action Cards: `/poke-gap` responses attach Telegram inline buttons for Agent, Improve, Poke research, and Health; `host:*` callbacks route to safe host actions; Poke research and empty-backlog Improve go through Action Planner instead of blocking or bypassing safety.
- L4.38 Provider Write Dedupe: provider write requests now use SHA-256 dedupe over connector, provider operation, and canonical request body; duplicates are blocked before request creation and again before network execution, legacy rows without stored keys are still detected, `write_blocked`/`verify_failed` do not permanently shadow retries, and duplicate execution writes a dry-run artifact with `external_write_performed=false`.
- L4.39 Poke Front Host Contract: `/poke-gap` and missed frustration fallback now return a shorter operator-style diagnosis with decision, facts, one next move, and no `/goal` redirect; `/chat` fallback can render the same diagnosis without writing `improvements.jsonl`, uses current task/error counts, and avoids false triggers such as `pokemon`.
- L4.40 Drive Document Executor: `/provider execute <request_id> <confirm>` can create a Google Docs document through Drive `files.create` multipart upload only after request approval, only with `AI_COUNCIL_PROVIDER_WRITE_ENABLED=true`, `AI_COUNCIL_DRIVE_FILE_WRITE_ENABLED=true`, and Google OAuth; it validates title/body/outline/folder, stores provider result artifacts with Drive `webViewLink`, and verifies them through the existing provider result verifier.
- L4.41 Provider Read-Before-Write: `/provider execute <request_id> <confirm>` now runs provider-specific reads before external write for GitHub issues, Gmail drafts, Calendar events, and Drive documents. Duplicate or failed preflight creates a `write_blocked` dry-run with `external_write_performed=false`; successful provider writes persist `provider_read_before_write` evidence in result artifacts.
- L4.42 Default Front Host: Poke/parity frustration now returns `Poke Gap L4.42`, does not redirect to long `/goal` dumps, reports L4.41 as done, names front UX/proactive ownership as the current gap, and routes more short ordinary questions to the front LLM while keeping status/system phrases local.
- L4.43 Autonomous Loop Cadence: `error_audit_twice_daily` and `feature_evolution_loop` are versioned system-managed recipes with `cadence=twice_daily`; `feature_evolution_loop` now runs at `10:15` and `22:15`; stale deployed recipe JSON files migrate to L4.43 while preserving `enabled`; `/loops` shows cadence, next windows, and last run.
- L4.44 One Contact Memory Front: deterministic local `/chat` fallback uses the latest conversation turn for the same Telegram chat, so follow-ups such as `a teraz krócej` and `co dalej` no longer sound like a fresh empty conversation when Grok front chat is gated; the Grok front prompt also treats Telegram as one continuous contact.
- L4.45 iPhone Shortcuts Service Pack: `/shortcuts` reports token state, endpoint, bind scope, payloads, recent tasks, and Windows start/status/stop scripts; Shortcuts HTTP `/health` returns the service version; deploy scripts use token gating and PID-file process verification; no Shortcuts daemon starts automatically.
- L4.46 Mobile Activation Advisor: `/agent` now surfaces missing `AI_COUNCIL_SHORTCUT_TOKEN` as a high-priority `iphone_setup` item with `NEXT: /shortcuts`; proactive scan can create a daily `iphone_setup` nudge; RUN fallback still surfaces the first safe runnable action without bypassing token setup or daemon approval.

## External Follow-up

No current GitHub publishing blocker. The broader Poke parity goal remains active because the front-host still needs to feel more like one personal operator, and iPhone/iMessage plus deeper integration-backed autonomy are not yet complete.
