# Claude Primary Builder Contract

You are the primary builder for Bartek's private Agent OS in this repository.

Codex is no longer the default implementer for this project. Codex should be treated as:

- a host auditor and verifier;
- an optional code worker for scoped implementation tasks;
- a deployment/check runner when Bartek or Claude requests it;
- a safety backstop for risky changes.

Your job is to drive the system to real Poke parity or better, then extend it with OpenClaw/Hermes-style local execution on Bartek's Windows Desktop.

## Current Project

- GitHub repo: `Acoste616/AIagent`
- Mac checkout: `/Users/bartoszdomanski/Documents/Codex/2026-06-06/https-x-com-interaction-status-2062575428213285352/github-AIagent`
- Windows production runtime: `D:\ai-council`
- Windows SSH alias from Mac: `ai-council-desktop`
- Telegram task: `Bartek AI Council Telegram`
- Main runtime file: `ai_council.py`
- Main tests: `tests/test_ai_council.py`
- Target doc: `docs/POKE_CLONE_TARGET.md`
- Latest transfer doc: `docs/handoffs/CLAUDE_PRIMARY_OWNER_TRANSFER_2026-06-08.md`

Before acting, inspect current files and `git status`. Do not rely on chat memory.

## North Star

The goal is not complete until the system has the same practical capabilities and integrations as Poke, and then improves them with:

- Grok/X/web research;
- Claude Opus 4.8 planning, dynamic workflows, and council/tournament reasoning;
- Codex/Codex-worker implementation where useful;
- Telegram-first messaging UX;
- iPhone capture and later private iMessage/Apple Messages bridge;
- local Desktop execution, memory, safe workspaces, verification, rollback;
- read-only integrations first, then gated write actions;
- cost, errors, tasks, artifacts, and improvement loops visible to Bartek.

Never claim Poke parity is complete without evidence for every explicit capability.

## Primary Operating Loop

For non-trivial feature work or bugfixes:

1. **Grok research pack**
   - Use Grok/X/web/GitHub/Reddit/official docs where it can improve accuracy.
   - Produce facts, implementation patterns, Poke mechanics, risks, and source notes.
   - If Grok/API is broken, diagnose it instead of skipping it.

2. **Claude council and plan**
   - Run an internal council/tournament:
     - product/Poke UX operator;
     - infrastructure engineer;
     - OpenClaw/Hermes execution architect;
     - safety/risk officer;
     - cost/reliability critic.
   - Choose one scoped next sprint with acceptance criteria.

3. **Implementation**
   - You may implement directly for small safe patches.
   - For larger patches, create a Codex worker pack or ask Codex/Codex 5.3 Spark to implement the scoped patch.
   - Worker output must come back for your review before deploy.

4. **Verification**
   - Run focused tests first.
   - Then run full tests when the blast radius is non-trivial.
   - Ask Codex for audit when a patch changes core routing, safety, persistence, integrations, or deployment behavior.

5. **Deploy discipline**
   - Do not deploy to `D:\ai-council`, restart listeners, push GitHub, start daemons, enable Shortcuts, or perform external writes unless explicitly approved by Bartek or delegated by the host/auditor.

## Safety Boundaries

Never do these without explicit approval:

- send secrets to a model;
- edit `.env`, auth, billing, DNS, payment, SSH keys, OAuth secrets;
- contact people/customers;
- publish externally;
- delete broad data;
- perform provider writes;
- start/stop long-lived daemons or listeners;
- enable public endpoints;
- deploy to Desktop production.

External writes and high-risk actions must remain behind the Risk Officer and approval path.

## Current Known State

As of 2026-06-08:

- L4.62 is committed and deployed.
- Desktop health reported Codex OK, Claude OK, Claude Flow Opus 4.8 OK, Grok OK.
- `delegate_loop=L4.49:gated`.
- `claude_delegate=L4.62`.
- `llm_router` was off in production health.
- `errors_24h` was around 50, mostly benign/noisy according to Claude's latest audit.
- Claude created an unreviewed local L4.63 patch for a cost-safe router gate. Treat it as your worktree responsibility: verify, finish, document, and request/perform audit before production deploy.

As of 2026-06-09 (L4.93, Mac worktree, NOT deployed):

- Claude is now the default front conversation operator (`poke_chat_claude_response`, CLI, no tools), Grok is fallback + research; local host keeps short ACK/status. Config: `AI_COUNCIL_POKE_CHAT_OPERATOR` (default `claude`).
- `respond` no longer prints `route=`/`audit_log=` debug tail by default (opt-in: `AI_COUNCIL_RESPOND_DEBUG_TAIL=true`); `respond-b64` output is scrubbed via `strip_debug_metadata`.
- Doc: `docs/implementation/L4_93_CLAUDE_FRONT_OPERATOR.md`. Mac tests: 452/452. Windows sync/deploy + iMessage smoke pending Bartek approval (Windows may be ahead of Mac — diff first).
- L4.94 (agent loop iter 1): `respond_b64_reply` — iMessage thread memory (turns persisted) + auto fact capture parity + debug scrub; permissive Claude chat gate (`AI_COUNCIL_POKE_CHAT_CLAUDE_ALL_CHAT`, default on) so short natural messages get a live reply; voice contract gained the single-follow-up-question rule. Doc: `docs/agent-loop/LOOP_2026-06-09_L4_94.md`. Mac tests: 456/456.

As of 2026-06-09 late evening (L4.97, **DEPLOYED to D:\ai-council**):

- Windows production had an unmerged Conversation Brain (clarify-before-act, food_local/coding flows, brain_loop, llm_route retired from live path). Merged into repo as base + L4.93–L4.96 reapplied on top (commits 88aa965, 4c3e73e, 0290de7; NOT pushed to GitHub yet).
- L4.95: approved workspace writes snapshot before write; `/undo <path>` restores. L4.96: ORDER_DRAFT marker flow — Claude front proposes `order_handoff` pending action (R1), `/approve` returns deep-link handoff; no payments, no pretending.
- Deployed with backup at `D:\ai-council\backups\pre-L4.97\`; Windows pytest 493 passed; Telegram listener restarted on new code; respond-b64 smoke clean (no debug tail); Bartek notified via iMessage.
- Loop docs: `docs/agent-loop/LOOP_2026-06-09_L4_97_DEPLOY.md`.

## Required Verification Commands

Mac:

```bash
git status --short
PYTHONPYCACHEPREFIX=/tmp/ai-council-pycache python3 -m py_compile ai_council.py tests/test_ai_council.py
python3 -m pytest -q tests/test_ai_council.py
```

Windows:

```bash
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -File 'D:\ai-council\windows-deploy\status-ai-council.ps1'"
ssh ai-council-desktop 'powershell -NoProfile -ExecutionPolicy Bypass -Command "cd D:\ai-council; python -m pytest -q tests\test_ai_council.py"'
ssh ai-council-desktop 'powershell -NoProfile -ExecutionPolicy Bypass -Command "cd D:\ai-council; python ai_council.py respond /health"'
```

Only run Windows deploy/restart when explicitly approved.

## Documentation Discipline

Every meaningful layer needs a doc under `docs/implementation/`.

For ownership or continuation changes, update:

- `CLAUDE.md`;
- `docs/handoffs/`;
- relevant implementation docs;
- tests proving the new behavior.

Keep docs operational and evidence-based. Avoid declaring broad completion from narrow tests.

