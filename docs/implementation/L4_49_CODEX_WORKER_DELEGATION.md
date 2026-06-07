# L4.49 Codex Worker Delegation

## Goal

L4.49 adds a cheaper implementation step without changing the product goal.

North Star remains: build a private Poke-like agent, then improve it with OpenClaw/Hermes-style local execution on Bartek's Desktop server. GPT/Codex and Claude are used through Bartek's subscriptions/OAuth where possible; Grok is used through API key for research/red-team.

## Loop

Required implementation loop:

1. Grok creates a source/research pack for Claude.
2. Claude Opus 4.8 reads Grok's materials, the local codebase, the Poke target, and OpenClaw/Hermes context.
3. Codex 5.3 Spark worker implements a scoped local patch.
4. Host Codex reviews diff, tests, optional Claude review, Windows deploy, and Telegram smoke.

Worker delegation is not a replacement for Grok, Claude, or host audit.

## Commands

- `/delegate <scope>` creates a delegation task and artifacts.
- `/delegate prepare <task_id>` runs Grok research then Claude plan and saves:
  - `grok-research.md`
  - `claude-plan.md`
- `/delegate prepare <task_id>` is idempotent after `prepared_for_worker`; use `--force` to intentionally re-run paid model calls.
- `/delegate run <task_id>` starts a local AI Council wrapper only when `AI_COUNCIL_CODEX_WORKER_ENABLED=true`; otherwise it prints the manual command. The wrapper runs the primary Codex model and retries once with the fallback model if the primary exits non-zero.
- `/delegate review <task_id>` shows host audit checklist and worker status.

Natural intent also routes phrases like `deleguj do codexa ...`, `codex worker ...`, and `spark agent ...`.

## Safety

Default auto-run is off:

```env
AI_COUNCIL_CODEX_WORKER_ENABLED=false
AI_COUNCIL_CODEX_WORKER_TIMEOUT=1800
```

Worker boundaries:

- no secrets or `.env` edits,
- no daemons/listeners/schedulers,
- no external write APIs,
- no push/deploy/publish,
- no contacts, money, DNS/auth/billing,
- host review required before deploy.

Runtime guards:

- `/delegate run` respects `/control`, global kill-switch, model pause, call limits, and budget guards through `reserve_operator_call("codex-worker")`.
- `/delegate run` refuses re-entry when the same task already has a running worker or an existing `worker-final.md`.
- `/delegate review` runs a local git status secret guard and blocks deploy review when real `.env`, SSH keys, tokens, credentials, or key files appear in the diff/status. `.env.example` is allowed as a public template.
- `workspace-write` is still prompt-bound and host-audited; it is not treated as a secure secret sandbox.

## Verification

Local checks:

- `python3 -m py_compile ai_council.py`
- `python3 -m pytest tests/test_ai_council.py -q -k "delegate or codex_worker or true_poke_target"`
- full `python3 -m pytest tests/test_ai_council.py -q`

Windows smoke after deploy:

- `/delegate dopracuj styl Poke frontu`
- `/delegate prepare <task_id>` only when a live model run is intended
- `/delegate run <task_id>` should stay gated unless worker auto-run is explicitly enabled
- `/delegate review <task_id>`
- `/health` should show `delegate_loop=L4.49:gated` or `armed`
