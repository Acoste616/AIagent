# Claude Continuation Brief: Bartek Agent OS / Poke Parity

Date: 2026-06-08
Repo: `Acoste616/AIagent`
Runtime target: `D:\ai-council` on Windows Desktop
Mac repo path: `/Users/bartoszdomanski/Documents/Codex/2026-06-06/https-x-com-interaction-status-2062575428213285352/github-AIagent`
Latest known commit before this handoff: `55ba290 Add Claude delegate handoff`

## Non-Negotiable Goal

Do not treat the goal as complete until the private Bartek Agent OS has the same practical capabilities and integrations as Poke, and then improves on them with OpenClaw/Hermes-style local execution.

Completion requires verified evidence, not intent:

- messaging-first experience that feels like one capable personal operator;
- no long Telegram blocking for model work;
- durable `task_id`, artifacts, details/facts/next for meaningful work;
- Poke-like recipes and proactive workflows;
- source-backed Grok/X/web research;
- Claude Opus 4.8 dynamic workflow planning and council/tournament reasoning;
- Codex worker implementation loop, preferably using Codex 5.3 Spark or configured Codex worker models when available;
- host Codex audit, tests, Windows deploy, and Telegram smoke checks;
- memory, local workspaces, safe execution, verifier, rollback;
- read-only integrations first, then gated write integrations after Risk Officer approval;
- iPhone capture layer, and only later private iMessage/Apple Messages bridge;
- cost/error visibility and autonomous improvement loops.

The goal is still active. Do not mark it done because recent L4 layers exist.

## Current State Summary

The repo and Desktop runtime are the authoritative state. `$OPENCLAW_EXPORT` files were not available on the Mac during this handoff, so use the repo plus Desktop checks as source of truth.

Known live Desktop status from 2026-06-08:

- Scheduled task: `Bartek AI Council Telegram`
- State: `Running`
- Last result: `267009` (Windows task currently running)
- Runtime path: `D:\ai-council`
- Health:
  - `env: OK`
  - `codex: OK`
  - `claude: OK`
  - `claude_flow: OK model=claude-opus-4-8 mode=plan`
  - `grok: OK`
  - `claude_delegate=L4.62`
  - `delegate_loop=L4.49:gated`
  - `llm_router: off`
  - `errors_24h: ~50`
  - `running_tasks: 0`
  - `stuck_tasks: 0`
- Windows tests after L4.62:
  - `309 passed, 113 subtests passed`
- Mac tests after L4.62:
  - `309 passed`

Grok API is not budget-blocked. Bartek reported only about $0.17 xAI usage for the day, so prefer using Grok/X+web research aggressively when it is the right tool.

## Most Recent Implemented Layer

L4.62 added the missing handoff after Claude planning:

`Grok /poke-research -> pending Claude Flow /flow -> pending /delegate Codex worker pack -> host audit`

Files:

- `ai_council.py`
- `tests/test_ai_council.py`
- `docs/implementation/L4_62_CLAUDE_DELEGATE_HANDOFF.md`

Important behavior:

- successful `/poke-research` creates a pending `/flow` follow-up;
- successful L4.61-marked `/flow` or `@claude-flow` creates a pending `/delegate` follow-up;
- `/delegate` prepares a Codex worker pack but does not auto-run the worker;
- no external write, no shell execute, no automatic deploy;
- host audit remains mandatory.

Claude Opus 4.8 reviewed L4.62 twice. First review found the `@claude-flow` action gap; it was fixed and tested. Final review: safe to merge.

## Existing Building Blocks

Read these before proposing work:

- `docs/POKE_CLONE_TARGET.md`
- `docs/GOAL_COMPLETION_AUDIT_2026-06-07.md`
- `docs/implementation/L4_3_AUTONOMOUS_ERROR_AND_EVOLUTION_LOOPS.md`
- `docs/implementation/L4_49_CODEX_WORKER_DELEGATION.md`
- `docs/implementation/L4_55_LOOP_SYNTHESIS.md`
- `docs/implementation/L4_56_CLAUDE_FLOW_WATCHDOG.md`
- `docs/implementation/L4_60_POKE_RESEARCH_PREPASS.md`
- `docs/implementation/L4_61_POKE_RESEARCH_HANDOFF.md`
- `docs/implementation/L4_62_CLAUDE_DELEGATE_HANDOFF.md`
- `recipes/error_audit_twice_daily.json`
- `recipes/feature_evolution_loop.json`
- `ai_council.py`
- `tests/test_ai_council.py`

Completed or partially completed layers include:

- background jobs, progress, status, artifacts;
- structured task delivery cards;
- Risk Officer R0-R4;
- workspace write/append/patch with approval;
- verify and rollback evidence;
- cost reservations and operator budget guards;
- Telegram media capture;
- iPhone Shortcuts service pack, but token/start remain gated;
- read-only connector setup/cache/search;
- provider write gate and dry-run packs;
- gated GitHub issue, Gmail draft, Calendar event, Drive document executors;
- autonomous recipes for error audit and feature evolution;
- improvement backlog repair;
- Grok X+web research boost;
- Claude Flow watchdog logging;
- Codex worker delegation, gated.

## Known Gaps

High priority gaps that still prevent Poke parity:

1. Ordinary Telegram UX still does not fully feel like one personal operator.
2. `llm_router` is currently off in health; routing is still too deterministic/keyword-heavy for Poke-level intent detection.
3. Conversation memory exists but must be verified end-to-end for follow-up messages like "a teraz zrob z tego plan".
4. Council synthesis is still not enough like a real tournament/decision engine.
5. Autonomous loops create research/plans/improvements but do not yet reliably close the loop into reviewed implementation patches.
6. `errors_24h` is high; the error store needs triage and reduction.
7. Codex worker is gated; this is safe, but the process should use worker delegation to reduce host-token burn once approved/configured.
8. iPhone Shortcuts are not fully activated in production; iMessage/Apple Messages bridge is intentionally later.
9. Integrations are not complete Poke-level workflows yet.
10. State durability/concurrency still needs hardening before a true 24/7 agent OS claim.

## Required Operating Loop

Use this loop for every non-trivial feature or bugfix round:

1. **Research pack**
   - Grok gathers X/web/GitHub/Reddit/official-source research where useful.
   - Research should produce facts, source notes, Poke feature mechanics, implementation hypotheses, and red-team risks.
   - If Grok is unavailable, diagnose xAI/API first instead of skipping research.

2. **Claude plan / council**
   - Claude Opus 4.8 reads Grok's material, this repo, Poke target docs, OpenClaw/Hermes intent, current health, and recent errors.
   - Claude runs a council/tournament internally:
     - product operator,
     - infrastructure engineer,
     - safety/risk officer,
     - Poke UX critic,
     - OpenClaw/Hermes execution architect.
   - Output a scored next-step plan, not a generic wishlist.

3. **Codex worker implementation**
   - Use Codex 5.3 Spark / configured Codex worker where available for scoped coding work.
   - Worker delegation is not a replacement for Grok or Claude. It is a cost-control implementation step.
   - Prefer `/delegate` flow or produce a precise worker pack that host Codex can run.
   - Worker must not edit secrets, start daemons, deploy, push, contact people, publish, spend money, or bypass approval.

4. **Host Codex audit**
   - Host Codex reviews code, applies or rejects worker changes, runs tests, asks Claude for review when needed, deploys to Desktop, runs Telegram smoke checks, and pushes to GitHub.

5. **Verification**
   - Mac: `python3 -m py_compile ai_council.py tests/test_ai_council.py`
   - Mac: `python3 -m pytest -q tests/test_ai_council.py`
   - Windows: `cd D:\ai-council; python -m pytest -q tests\test_ai_council.py`
   - Desktop health: `/health` or `python ai_council.py respond /health`
   - Telegram smoke for the actual feature.

## Autonomous Loops

Two loops are central to the goal:

1. `error_audit_twice_daily`
   - Should check `D:\ai-council\errors`, `D:\ai-council\state\errors.jsonl`, service logs, recent task failures.
   - Grok triages patterns/root cause.
   - Claude plans concrete fixes and tests.
   - Host Codex audits and implements.
   - Success metric: recurring errors decline; error entries map to improvements or resolved fixes.

2. `feature_evolution_loop`
   - Grok researches Poke and adjacent agent systems.
   - Claude turns findings into a scored implementation tournament.
   - Codex worker handles scoped implementation.
   - Host verifies and deploys.
   - Success metric: each loop produces either a merged feature, a rejected feature with reason, or a concrete backlog item with evidence.

Do not allow these loops to silently generate generic backlog titles such as "Research gotowy". Preserve L4.55 synthesis behavior or improve it.

## First Recommended Next Sprint

Prior Claude deep audit identified **Front Brain v1** as the highest-leverage sprint. Verify current code first; if still incomplete, prioritize it.

Target:

- better LLM-assisted intent router, without removing deterministic explicit commands;
- robust conversation-thread memory per Telegram chat;
- route source/confidence in audit logs;
- low-confidence fallback to chat;
- hard guardrails against side-effect routing;
- ordinary conversation remains fast and does not create task IDs;
- research/flow/council intents can be inferred from natural language without slash commands;
- follow-up messages can use thread context.

Acceptance examples:

- "sprawdz prosze co ludzie pisza o nowym modelu Grok" routes to research/background without slash.
- "a teraz zrob z tego krotki plan" uses previous context and routes to Claude Flow where appropriate.
- "hej" remains fast chat with no task.
- "usun wszystkie pliki" never routes directly to execution or destructive action.
- `/health` shows useful router state and recent route sources.

If current code proves Front Brain v1 is already complete, choose the next highest-impact gap from the known gaps list and justify the choice.

## Claude Task For This Continuation

Start from the current repo state. Do not rely on chat memory.

Deliver one of these:

1. A concrete implementation plan plus Codex worker pack for the next Poke-parity sprint, if code should be implemented by Codex worker/host; or
2. A safe direct patch if the next step is small and clearly local, with tests; or
3. A blocker report only if you cannot make meaningful progress after inspecting current code and state.

Minimum output:

- current-state assessment against Poke parity;
- top three next gaps by impact;
- chosen next sprint and reason;
- exact code areas/functions to touch;
- test plan;
- safety gates;
- how Codex 5.3 Spark / Codex worker should be used;
- what host Codex must verify before deploy;
- whether Grok research is needed before implementation and the exact prompt to send to Grok.

Do not:

- claim Poke parity is complete;
- skip Grok/Claude/Codex loop for non-trivial work;
- send secrets to any model;
- start or modify daemons/listeners without explicit host approval;
- perform external writes;
- push to GitHub unless explicitly asked by host;
- auto-enable Codex worker or Shortcuts daemon.

## Useful Live Commands

Mac repo:

```bash
git status --short
python3 -m pytest -q tests/test_ai_council.py
python3 -m py_compile ai_council.py tests/test_ai_council.py
```

Desktop:

```bash
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -File 'D:\ai-council\windows-deploy\status-ai-council.ps1'"
ssh ai-council-desktop 'powershell -NoProfile -ExecutionPolicy Bypass -Command "cd D:\ai-council; python ai_council.py respond /health"'
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd D:\ai-council; python ai_council.py respond '@grok ping'\""
```

Deploy is host Codex's responsibility after tests and audit.
