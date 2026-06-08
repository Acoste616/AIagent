# MASTER GOAL — Poke++ (Bartek Agent OS)

Owner: Claude Code Opus 4.8 (primary builder)
Auditor / tester / deploy-checker: Codex
Date set: 2026-06-08
Status: ACTIVE — not complete. Do not mark done from partial layers.

This is the durable north-star `/goal` that Claude executes toward. It restates
the operator's intent and binds it to acceptance criteria, the build loop, and
safety gates. It supersedes nothing in `CLAUDE.md`; it is the "why" those rules
serve. Related: `docs/POKE_CLONE_TARGET.md`, `docs/GOAL_COMPLETION_AUDIT_2026-06-07.md`.

## Operator intent (verbatim sense)

> Build Poke — but better. The assistant has access to **Claude and GPT through
> Bartek's subscriptions** and to **Grok through the xAI API**. It must have:
> **memory like Hermes**, **hands (local execution) like OpenClaw**, and
> **functions, responses, and integrations like Poke**. Work step by step. Use
> **Grok for research** and gathering information about features/solutions.
> **Codex may write code.** Claude plans, audits, gathers information, and
> verifies that things actually work.

## Primary acceptance (operator's words, 2026-06-08)

> "/goal = a fully working system on my iPhone."

Concretely: Bartek uses it **daily from his iPhone** and it feels like Poke — texts one persona (today via Telegram on iPhone; later iPhone Shortcuts capture, then a private iMessage/Apple Messages bridge), it remembers his facts, runs background work with artifacts, proactively follows up, and acts on integrations behind approval. The build runs as a continuous loop (Grok/web research → Claude council/plan → Codex worker implementation → Claude review/audit → host test/deploy) until this is real and evidenced. Every layer is judged by: "does this make the iPhone experience materially closer to Poke-or-better?"

## What "done" means (no partial-credit completion)

The goal is complete only when ALL of these are real and evidenced, not just scaffolded:

### A. Poke-class product feel
- Texting feels like ONE capable personal operator, not a slash-command bot.
- Ordinary chat is fast and creates no `task_id`; long work never blocks Telegram.
- Every meaningful task yields `task_id`, progress, artifacts, and a Status/Details/Facts/Next card.
- Recipes / automations: reusable user-level workflows with triggers and outputs.
- Proactive follow-ups and topic ownership (nudges that are useful, not noise).
- Cost and model usage are visible (Poke's #1 complaint is cost opacity — we beat it).

### B. Hermes-class memory
- Durable per-contact memory: "one continuous contact" across messages and days.
- Follow-ups resolve against context ("a teraz zrób z tego plan" uses the prior turn).
- Source-backed recall (facts carry where they came from); consolidation over time.
- Memory is verified end-to-end with tests AND a live Telegram smoke, not assumed.

### C. OpenClaw-class hands (safe local execution)
- Safe local desktop execution on the Windows host: file/workspace ops, commands.
- Risk Officer R0–R4, approval gates, dry-run, verify, rollback, audit log.
- External writes and high-risk actions stay behind explicit approval.

### D. Models & research
- Claude (Opus 4.8) plans, runs council/tournament reasoning, audits, verifies.
- GPT/Codex implements scoped code as a worker (cost-control), then Claude reviews.
- Grok (xAI API) does source-backed X/Twitter + web research for every non-trivial round.

### E. Channels & integrations
- Telegram-first; iPhone capture (Shortcuts); later a private iMessage/Apple Messages bridge.
- Read-only integrations first (Gmail/Calendar/Drive/GitHub), then approval-gated writes.

### F. Operations
- 24/7 stability on the Windows Desktop runtime (`D:\ai-council`).
- Error/cost visibility; autonomous improvement loops that close into reviewed patches.

## The build loop (run every non-trivial round)

1. **Grok research** — X/Twitter + web + GitHub + Reddit + official docs. Produce
   facts, patterns, Poke mechanics, risks, sources. If Grok/API is broken, diagnose it.
2. **Claude council/plan** — internal multi-role council (Poke UX, infra engineer,
   OpenClaw/Hermes execution architect, safety/risk officer, cost/reliability critic).
   Output ONE scored next sprint with acceptance criteria.
3. **Implementation** — Claude for small safe patches; otherwise a Codex worker pack /
   Codex 5.3 Spark. Worker output returns to Claude for review before deploy.
4. **Verification** — focused tests → full tests → (host-approved) Windows tests →
   Telegram smoke for the exact behavior.
5. **Audit & report** — changed files, why it advances parity, tests + results, risks +
   approval gates, whether Desktop deploy is needed, exact Codex audit request, exact
   Grok prompt for next round, exact next command for Bartek.

## Safety gates (never without explicit approval)

- No deploy to `D:\ai-council`, no listener/daemon restart, no GitHub push, no Shortcuts enable.
- No external/provider writes; no editing `.env`/auth/billing/DNS/SSH/OAuth secrets.
- No sending secrets to any model; no contacting people; no broad deletes; no public endpoints.
- Paid model calls (incl. live Grok) are bounded and disclosed; the cost ledger stays truthful.

## How progress is tracked

- Each layer gets a doc under `docs/implementation/` with evidence.
- This file is updated when the goal definition or status materially changes.
- The live roadmap of upcoming layers is maintained from the council/synthesis output
  (see the round report under `docs/reports/` / `docs/handoffs/`).
- "Poke parity" is never claimed without evidence for every capability in section "done".
