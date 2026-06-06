# AI Council L2.6 Poke UX Implementation

Date: 2026-06-06
Target runtime: `D:\ai-council` on Windows Desktop

## Outcome

L2.6 is deployed on the Windows Desktop AI Council service. This is not a full
Poke clone yet, but it closes the first Poke-core gap: the Telegram bot now has
action buttons, a recipe MVP, Grok X research routing, delivery nudges, and a
clearer cost/status surface.

## Research Inputs

- Grok X research: `docs/research/grok-x-poke-research-2026-06-06.md`
- Claude Opus 4.8 full research plan:
  `docs/research/claude-opus48-poke-research-full-2026-06-06.md`
- Claude Opus 4.8 tournament scorecard:
  `docs/research/claude-opus48-tournament-scorecard-2026-06-06.md`

Claude's first short tournament output was rejected because it was only a
summary and did not provide a usable implementation scorecard. The accepted
scorecard chose Hybrid Staged Architecture as the best path, with Recipes-first
Poke clone as the runner-up.

## Implemented

- Telegram inline buttons for task status/details/cancel.
- Telegram inline buttons for pending action approve/deny.
- Callback handling with allowlist checks for Bartek only.
- `/recipes` and `/recipe show <name>`.
- Background `/recipe run <name> <input>`.
- Seed recipes:
  - `research_brief`
  - `daily_system_digest`
  - `project_next_action`
- Grok X research commands:
  - `@xresearch`
  - `/xresearch`
  - `/poke-research`
- Cost view with total calls, blocked calls, total runtime, and estimated USD.
- Pending-action nudges after a configurable delay.
- Capabilities/status labels updated to L2.6.

## Verified

Local repository:

```text
Ran 43 tests in 0.093s
OK
```

Windows Desktop deployment:

```text
Bartek AI Council Telegram: Running
running_tasks: 0
stuck_tasks: 0
codex: OK
claude: OK
claude_flow: OK model=claude-opus-4-8 mode=plan
grok: OK
```

Windows tests also passed with 43/43 tests.

## Still Missing for Full Poke/OpenClaw

- Voice note ingestion and transcription.
- Share sheet / iPhone Shortcuts endpoint.
- Rich recipe scheduler and recipe enable/disable commands.
- Full risk officer R0-R4 before broader execution.
- Workspace executor with verify/rollback for local side effects.
- Read-only Gmail, Calendar, GitHub, Drive integrations with cited sources.
- Apple Messages / iMessage bridge.
- Public Apple Messages for Business path.
- Dashboard and analytics.

## Current Boundaries

The system still blocks shell execution, external writes, publishing, contact
actions, money, DNS, auth, billing, and destructive operations unless explicit
approval and the later Risk Officer layer exist.

## GitHub Status

The project is prepared locally for `Acoste616/AIagent`, but pushing is blocked
until GitHub auth is refreshed. Known fixes:

```text
gh auth login -h github.com
```

or re-authorize the GitHub connector in Codex.
