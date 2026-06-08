# Claude Primary Owner Transfer

Date: 2026-06-08
Owner: Claude Code Opus 4.8
Auditor/backup: Codex
Project: Bartek Agent OS / Poke-like OpenClaw-Hermes AI Council

## Transfer Statement

Claude now owns ongoing project construction.

Codex's role changes from primary builder to:

- audit and review;
- test/deploy runner when requested;
- scoped implementation worker when Claude delegates;
- safety verifier for risky changes;
- final production deployment checker.

Claude should not wait for Codex to decide every next feature. Claude should inspect the repo, run the Grok/Claude/Codex loop, choose the next highest-impact sprint toward Poke parity, implement or delegate it, test it, and produce deploy-ready work with clear audit notes.

## What Claude Must Know

The current source of truth is the repo plus production Desktop state:

- Repo: `Acoste616/AIagent`
- Mac checkout: `/Users/bartoszdomanski/Documents/Codex/2026-06-06/https-x-com-interaction-status-2062575428213285352/github-AIagent`
- Production runtime: `D:\ai-council`
- SSH alias: `ai-council-desktop`
- Telegram Scheduled Task: `Bartek AI Council Telegram`
- Main code: `ai_council.py`
- Main tests: `tests/test_ai_council.py`
- Target: `docs/POKE_CLONE_TARGET.md`
- Previous handoff: `docs/handoffs/CLAUDE_CONTINUATION_BRIEF_2026-06-08.md`
- Primary builder contract: `CLAUDE.md`

`$OPENCLAW_EXPORT` was unavailable from the Mac during the last Codex run, so if it is still missing, do not block. Use the repo, Desktop runtime, and project docs as source of truth.

## Current Worktree

Claude already created an unreviewed L4.63 patch:

- `ai_council.py`
- `tests/test_ai_council.py`
- `docs/implementation/L4_63_FRONT_BRAIN_V2_COST_SAFE_ROUTER.md`

This patch appears to change the LLM router cost gate:

- adds `SMALLTALK_PHRASES`;
- adds `is_smalltalk()`;
- changes `llm_router_should_try()` from keyword-positive gating to smalltalk/short-noise negative gating;
- adds three routing tests.

Claude must treat this as in-progress work:

1. re-read the diff;
2. run focused and full Mac tests;
3. ask Codex or Claude review if safety-sensitive;
4. decide whether to revise;
5. only then prepare it for host deploy/audit.

Do not silently assume the patch is production-ready just because tests passed in the prior run.

## Final Goal

Build a private Bartek Agent OS that has Poke's practical capabilities and then exceeds them:

- normal messaging, not command-bot feel;
- one contact/personality in Telegram/iPhone;
- background work with progress and artifacts;
- recipes and proactive workflows;
- memory and source-backed context;
- Grok X/web research;
- Claude dynamic planning and council/tournament reasoning;
- Codex worker implementation loop;
- local Desktop execution like OpenClaw/Hermes;
- read-only integrations first, then approval-gated writes;
- iPhone capture now, iMessage/Apple Messages later;
- visible costs, errors, tasks, and improvement loops;
- 24/7 stability on Windows Desktop.

## Build Loop Claude Must Run

For every substantial round:

1. **Grok research**
   - Prompt Grok to research Poke features, X threads, GitHub, Reddit, official docs, agent patterns, implementation mechanics, and risks.
   - Use Grok also for red-team and error triage.

2. **Claude council**
   - Claude runs an internal multi-role council and picks one sprint.
   - Required roles:
     - Poke UX critic;
     - agent infrastructure engineer;
     - OpenClaw/Hermes local-execution architect;
     - safety/risk officer;
     - product operator for Bartek;
     - cost/reliability critic.

3. **Implementation**
   - Small safe patches: Claude may implement directly.
   - Larger patches: Claude should create a Codex worker pack or delegate to Codex/Codex 5.3 Spark for implementation.
   - Worker patches must be reviewed by Claude and then audited by Codex before production deploy.

4. **Verification**
   - Targeted tests.
   - Full Mac tests.
   - Windows tests after host-approved copy/deploy.
   - Telegram smoke for the exact behavior.

5. **Deploy**
   - Deployment to `D:\ai-council`, restart, GitHub push, and enabling daemons remain gated unless Bartek explicitly grants Claude that authority.

## Immediate Next Action For Claude

Continue from the current dirty worktree.

1. Audit the L4.63 router patch.
2. Verify whether it moves toward Poke parity.
3. If good, finish the doc/tests and prepare a host-audit report.
4. If flawed, fix it.
5. Then propose the next sprint:
   - likely L4.64, either:
     - router production enablement plan and Telegram smoke matrix;
     - double-call optimization for route+answer;
     - real Council synthesis;
     - loop closure from improvement to patch;
     - error signal hygiene.

## What Claude Should Produce At The End Of Each Round

Every round should end with:

- changed files;
- why this matters for Poke parity;
- tests run and results;
- risks and approval gates;
- whether Desktop deploy is needed;
- exact Codex audit request;
- exact Grok research prompt for the next round if needed;
- exact next command or task for Bartek.

## What Codex Should Do Now

Codex should not keep implementing by default.

Codex may:

- create this transfer document;
- start/resume Claude primary-owner task;
- audit Claude's finished patch;
- run tests/deploy after explicit approval;
- help with narrow worker implementation if Claude delegates.

Codex should not overwrite Claude's dirty worktree changes.

