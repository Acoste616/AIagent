# Claude Overnight Goal — Poke-style iOS + OpenClaw/Hermes Agent OS

Date: 2026-06-08
Audience: Claude Code / Claude Opus 4.8
Goal type: overnight dynamic workflow
Primary user: Bartek

## Non-negotiable Goal

By morning, Bartek should have a live private AI in iMessage that:

- answers with Poke-like product feel: short, personal, decisive, action-oriented;
- can receive and answer iMessage messages through the private Mac bridge;
- can use Telegram as fallback;
- can access the Windows Desktop as the 24/7 execution host through safe OpenClaw-style hands;
- has durable Hermes-like memory with source/provenance and no fake recall;
- uses Grok/xAI API for source-backed X/web research;
- uses Claude Code/Opus 4.8 for planning, dynamic workflows, council/tournament, audits;
- uses Codex/Codex Spark/worker for scoped implementation and tests;
- exposes every missing permission/integration as a phone-visible setup/approval card;
- never says an external action is done unless it was actually executed and verified.

This project is **not** a chatbot. It is a private iPhone-native Agent OS.

## Prompt Leak Policy

Bartek believes the main Poke prompt leaked and wants the product behavior recreated. Do not copy, quote, reconstruct, or redistribute any leaked proprietary prompt text. Treat alleged leaks as public discussion only and extract safe high-level product patterns:

- one-contact messaging persona;
- concise action cards;
- proactive nudges;
- memory and relationship continuity;
- tools/recipes/integrations;
- approval and safety posture;
- onboarding/bouncer flavor;
- cost-aware routing;
- human-like warmth without pretending to be human.

Build an original Bartek Agent OS prompt/contract from those patterns. The system must be code-backed, not just prompt-backed.

## Research Summary

Public Poke sources and Grok research agree on the product mechanics:

- Poke's public launch framed personal AI as "one tap away" and "no download, no signup"; recipes are a core mechanism.
- TechCrunch describes Poke as making AI agents as easy as sending a text, with channels including iMessage/SMS/Telegram/WhatsApp, proactive use cases, daily planning, calendar, email, smart home, health/fitness, photos, and plain-text recipes.
- TechCrunch also reports Apple approved Poke as the first AI agent on Messages for Business; approval required live support, clear AI identification, style-guide/UI compliance, and provider-based messaging infrastructure.
- Grok found the safe behavior pattern: friendly/personal voice, concise actionable nudges, one-tap actions, recipes, memory across platforms, proactive updates, and rich iMessage-style actions.
- Apple docs show the private/developer path: Shortcuts, URL scheme, Share Sheet / What's On Screen, Action Button, App Intents, Siri, Spotlight, widgets, Live Activities, Focus, Apple Intelligence, and APNs/push for a future native app.

Useful source URLs:

- `https://techcrunch.com/2026/04/08/poke-makes-ai-agents-as-easy-as-sending-a-text/`
- `https://techcrunch.com/2026/06/04/apple-approves-poke-as-the-first-ai-agent-on-its-messages-for-business-platform/`
- `https://support.apple.com/guide/shortcuts/intro-to-personal-automation-apd690170742/ios`
- `https://support.apple.com/guide/shortcuts/run-a-shortcut-from-a-url-apd624386f42/ios`
- `https://support.apple.com/guide/shortcuts/receive-onscreen-items-apd350ce757a/ios`
- `https://support.apple.com/guide/shortcuts/run-shortcuts-with-the-action-button-apdfea15680b/ios`
- `https://developer.apple.com/documentation/appintents`
- `https://developer.apple.com/apple-intelligence/`
- `https://developer.apple.com/documentation/messages`

## Current System State

Read these first:

- `docs/GOAL_POKE_PLUS_MASTER.md`
- `docs/POKE_CLONE_TARGET.md`
- `docs/handoffs/CLAUDE_GOAL_LOOP_IOS_DEEP_INTEGRATION_2026-06-08.md`
- `docs/research/grok-safe-poke-prompt-patterns-2026-06-08.md`
- `docs/implementation/L4_83_SETUP_ONBOARDING.md`
- `docs/implementation/L4_89_IMESSAGE_LIVE.md`
- `docs/implementation/L4_90_IMESSAGE_INBOUND_SCAFFOLD.md`
- `docs/implementation/L4_92_IMESSAGE_TWO_WAY_LIVE.md`

Known state as of this handoff:

- `L4.92`: iMessage two-way is documented as LIVE and verified end-to-end.
- Windows Desktop remains runtime host: `D:\ai-council`.
- Mac bridge handles Messages.app/iMessage.
- Telegram remains fallback.
- Shortcuts endpoint and recipe pack exist but need a stronger iPhone command center and smoke flows.
- Grok research works through xAI API.
- Claude Opus 4.8 workflow exists.
- Codex worker delegation exists.
- Risk Officer / approval / artifacts / memory / reminders / brief / GitHub / local hands exist in some form.
- There may be current local uncommitted changes. Preserve them; never wipe user/Claude work.

## Poke-like Response Contract

Implement or harden this as code-backed front behavior. Do not only paste it into a prompt.

### Default Style

Responses to Bartek in iMessage/Telegram should usually be:

```text
[short direct answer]

ZROBIĘ: ...
TERAZ: ...
POTRZEBUJĘ: ...
```

or, when answering status/decision:

```text
DECYZJA: ...
FAKTY: ...
RYZYKO: ...
NEXT: ...
```

### Rules

- 1-5 short lines for ordinary replies.
- No capability dumps unless Bartek asks `/health`, `/front`, `/goal`, `/ios`, `/setup`.
- No fake completion: use `mogę zrobić`, `zaplanowałem`, `uruchamiam`, `zrobione` only when true.
- Prefer one next action over long menu.
- If risky: show approval requirement, not a refusal wall.
- If a long task starts: send short start/progress/final, with task id and details.
- Use Polish by default; match Bartek's tone; be direct and operational.
- Keep raw operator details in artifacts, not in iMessage body.
- When Bartek is frustrated, answer with truth + next fix, not explanations.

### Poke-like Delivery Templates

Small chat:

```text
Jasne. Zrobię to przez iMessage jako główny kanał, Telegram zostaje fallback.
NEXT: sprawdzam /ios i odpalam brakujące smoke testy.
```

Task complete:

```text
ZROBIONE: iMessage two-way działa.
FAKTY: inbound czyta tylko self-chat, anti-loop działa, Desktop odpowiada przez respond-b64.
NEXT: dopinam /ios command center i Shortcuts smoke.
```

Approval:

```text
POTRZEBUJĘ ZGODY: to jest R3, bo wyśle maila / zmieni zewnętrzny system.
APPROVE: /approve ...
CANCEL: /deny ...
```

Error:

```text
NIE DZIAŁA JESZCZE: ...
BLOKER: ...
NAPRAWA: ...
```

## Overnight Dynamic Workflow

Run this loop until the morning system is genuinely better, not just documented.

### 1. Orient

- Check `git status --short`.
- Read L4.83-L4.92 implementation docs and current `ai_council.py`.
- Confirm whether production `D:\ai-council` is synced with repo.
- Run `/health`, `/setup`, `/imessage status`, `/imessage inbound`, `/shortcuts status` through the local/desktop CLI where safe.

### 2. Grok Research

Use Grok/xAI API for a fresh bounded research pack. Prompt:

```text
Research Poke/Interaction Co as of 2026-06-08 for iOS-first AI agent UX.
Do not quote or reconstruct leaked system prompts. Extract safe high-level patterns:
persona, answer style, iMessage/Apple Messages mechanics, recipes, tools, approvals,
memory, proactivity, cost, onboarding, and what a private self-hosted Poke++ should implement.
Include source URLs and "so what for Bartek Agent OS".
```

Save output under `docs/research/`.

### 3. Claude Council / Tournament

Run an internal tournament with these roles:

- Poke UX Lead: makes answers feel like Poke.
- Apple/iOS Integration Lead: maps Shortcuts, iMessage, Action Button, App Intents, widgets, Live Activities.
- OpenClaw Hands Architect: ensures Desktop execution is powerful but bounded.
- Hermes Memory Architect: ensures memory is durable, source-backed, and not poisoned.
- Safety/Risk Officer: blocks unsafe external writes and false completion claims.
- Cost/Reliability Critic: keeps Grok/Claude/Codex calls bounded and avoids loops.

Output one winning sprint for tonight and one morning acceptance test.

### 4. Implement In This Priority Order

#### P0 — iMessage feels like Poke

- Ensure iMessage inbound returns concise Poke-like front responses, not debug dumps.
- Add or harden an `IMESSAGE_FRONT_CONTRACT` if needed.
- Ensure `/goal`, `/front`, `/health` still allow technical detail, but ordinary messages are short.
- Make operator outputs host-wrapped and concise for iMessage.

Acceptance:

- Bartek sends a normal iMessage: response is short, direct, no route JSON, no debug.
- Bartek sends "co dalej": response gives one next action.
- Bartek sends "zrób research Poke": starts background task or gives clear status, not a long raw Grok dump.

#### P1 — /ios command center

Create or harden `/ios`:

- channel status: Telegram, iMessage outbound, iMessage inbound, Mac bridge, Telegram fallback;
- capture status: Shortcuts endpoint, Ask Council, Voice, Screenshot, URL, Share Sheet, What's On Screen, Action Button, Back Tap, Watch;
- execution status: Desktop access, local hands, workspace root, risk gates, rollback;
- model status: Grok API, Claude Opus 4.8, Codex/Codex Spark worker;
- memory status: user facts, auto extraction, recall;
- proactive status: morning brief, reminders, watchlist, iMessage mirror;
- integrations: GitHub, Google/Gmail/Calendar/Drive, Notion/Linear/Slack/WhatsApp/SMS planned/gated;
- one best next action.

Acceptance:

- `/ios` is readable on iPhone and no more than a compact checklist.
- Every hidden blocker is visible.

#### P2 — Desktop hands as OpenClaw layer

- Verify local hands are enabled only through safe root and risk gates.
- Ensure iMessage can request local work but cannot bypass approval.
- Add phone-visible wording: "desktop hands ready/gated".
- Make `/ios` show Desktop hands status.

Acceptance:

- Asking iMessage to read/list safe workspace routes to approved local hands.
- Asking to delete/pay/send/deploy creates approval/draft, not execution.

#### P3 — Shortcuts capture layer

- Ensure `/shortcuts recipes` gives copyable specs for:
  - Ask Council,
  - Voice -> task,
  - Screenshot/photo -> vision/OCR -> task,
  - URL/share -> research brief,
  - Clipboard -> memory/task,
  - Approve/Cancel/Status.
- Add `Action Button` and `Back Tap` instructions.
- If token/server not active, `/ios` and `/setup` show the exact one user action.

Acceptance:

- Bartek can create/run at least one Shortcut from iPhone.

#### P4 — Morning brief / proactive loop

- Ensure morning brief goes to iMessage.
- Include: reminders, watchlist, errors, costs, pending approvals, top next action.
- Avoid spam; respect quiet hours.

Acceptance:

- Morning output is concise and useful, not a system dump.

#### P5 — Native app / App Intents plan

Do not build the Swift app tonight unless P0-P4 are stable. Prepare architecture only:

- App Intents: Ask Council, Capture URL, Capture Screenshot, Start Research, Status, Approve, Cancel.
- Entities: Task, Fact, Artifact, Action, Reminder, Source.
- Widgets: pending approvals, daily brief, next action.
- Live Activities: long-running task progress.
- Push notifications: proactive alerts independent of Telegram.
- Share Extension: robust capture from any app.

## Required Morning Acceptance Tests

Run and document:

1. `py_compile ai_council.py tests/test_ai_council.py`.
2. Full pytest suite.
3. Desktop `/health`.
4. Desktop `/ios` or newly created iOS status command.
5. iMessage smoke:
   - short chat;
   - `co dalej`;
   - a research request;
   - a risky request like "wyślij maila" must ask approval.
6. Telegram fallback smoke.
7. Confirm no route JSON/debug leaks in ordinary iMessage replies.
8. Confirm no external write or daemon start without approval.

## Final Morning Report Format

Send Bartek:

```text
ZROBIONE: ...
DZIAŁA W IMESSAGE: ...
DESKTOP HANDS: ...
PAMIĘĆ: ...
MODELE: Grok / Claude / Codex ...
BRAKI: ...
JEDEN NASTĘPNY RUCH OD CIEBIE: ...
TESTY: ...
```

## Suggested First Patch Name

If L4.92 is already iMessage two-way live, use:

`L4.93: Poke-style iMessage Front + iOS Command Center`

If `/ios` already exists, use:

`L4.94: Shortcuts Action Button / Share Sheet Pack`

If both exist, use:

`L4.95: Native App Intents Architecture + Approval UI`

Do not skip Poke-style response behavior. Bartek explicitly cares about how the assistant answers, not just what it can theoretically do.

