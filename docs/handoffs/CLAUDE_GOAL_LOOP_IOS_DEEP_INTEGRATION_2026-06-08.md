# Claude Goal Loop — Deep iOS Integration

Date: 2026-06-08
Owner target: Claude Opus 4.8 as primary builder
Project: Bartek Agent OS / AIagent / Poke++ / OpenClaw-Hermes iPhone layer

## Research Basis

Current focus changed from generic Poke parity to the deepest possible private iOS integration. The target is not "a Telegram bot with extras"; the target is one iPhone-native personal AI operating layer that can capture, understand, plan, execute, remember, notify, ask for approval, and use local Desktop capabilities safely.

Use these Apple facts as current constraints and opportunities:

- Shortcuts is the fastest private iOS ingress layer. Apple documents personal automations triggered by time, location, app-open, communication, transaction, and settings events. Source: `https://support.apple.com/guide/shortcuts/intro-to-personal-automation-apd690170742/ios`
- Shortcuts can be run from URL schemes with text or clipboard input, which gives us deep links from apps, browser, notes, task managers, and web surfaces. Source: `https://support.apple.com/guide/shortcuts/run-a-shortcut-from-a-url-apd624386f42/ios`
- Shortcuts can receive Share Sheet / "What's On Screen" input from supported apps such as Safari, Maps, and Photos, and this can be used through Siri or Back Tap. Source: `https://support.apple.com/guide/shortcuts/receive-onscreen-items-apd350ce757a/ios`
- Supported iPhones can bind the Action Button to a Shortcut. Source: `https://support.apple.com/guide/shortcuts/run-shortcuts-with-the-action-button-apdfea15680b/ios`
- App Intents is the long-term native integration layer. Apple says it exposes app content/actions to Siri, Spotlight, widgets, controls, Shortcuts, Action Button, Focus, Apple Intelligence, and Live Activities. Source: `https://developer.apple.com/documentation/appintents`
- Apple Intelligence developer docs say App Intents connects app actions/content to Siri and Apple Intelligence; Shortcuts can assemble automations from natural-language descriptions and app actions. Source: `https://developer.apple.com/apple-intelligence/`
- Public iMessage automation is not a normal iOS app API. Apple's Messages framework is for iMessage apps/stickers; public business messaging is a separate Apple Messages for Business path. For a private solo system, our practical path is the current Mac Messages.app bridge plus strict allowlist/audit. Source: `https://developer.apple.com/documentation/messages`

## Current Local State To Assume

Repo: `Acoste616/AIagent`
Runtime host: `D:\ai-council` on the Windows Desktop.
Mac bridge: used for Messages.app/iMessage and Mail.app style private bridge.

Recent layers already present in repo/status:

- L4.83 `/setup` onboarding checklist.
- L4.84 proactive iMessage mirror.
- L4.85 Bartek profile/topic watchlist.
- L4.86 morning brief surfaces reminders.
- L4.87 daily watchlist research digest in brief.
- L4.89 iMessage outbound channel live and persistent via launchd + Mac runner.
- L4.90 iMessage inbound/two-way scaffolding with Full Disk Access gate.
- L4.91 safe secret rotation helper.

Do not assume the project is complete. Poke parity is still active. The iOS layer is now the highest-priority path to product feel.

## Goal

Build the deepest possible private iOS integration for Bartek Agent OS.

Definition:

Bartek should be able to use his AI from iPhone as if it were a native, always-available personal operator:

- write or speak from iMessage, Telegram, Shortcuts, Siri, Action Button, Back Tap, Share Sheet, screenshot, URL, photo, voice note, and eventually native app surfaces;
- receive concise proactive iMessage/notification updates;
- approve/cancel risky actions from the phone;
- send any captured context to Grok/Claude/Codex/Council;
- have tasks, facts, artifacts, next actions, cost, and risks visible from the phone;
- let the Desktop execute local/OpenClaw/Hermes-style work safely behind Risk Officer gates;
- use Google/GitHub/Files/Mail/Calendar/Drive and later Notion/Linear/WhatsApp/SMS through explicit read/write policies;
- never claim a real action was done unless it was actually executed and verified.

"Everything" means maximum lawful/private iOS capability through Apple's supported surfaces plus the private Mac bridge. It does not mean bypassing platform security, scraping secrets, or silently sending/deleting/contacting/paying.

## Claude Loop Prompt

Paste this into Claude Code / Claude Opus 4.8:

```text
You are Claude Opus 4.8, primary builder and architect for Bartek Agent OS.

CURRENT NORTH STAR
Our focus is now DEEP IOS INTEGRATION. The system must become Poke-like or better on Bartek's iPhone: one private agent contact that can capture from iMessage/Telegram/Shortcuts/Siri/Action Button/Share Sheet/screenshots/voice/photos/URLs, reason with Grok+Claude+Codex, execute through the Windows Desktop/OpenClaw/Hermes layer, remember facts, run proactive loops, and request approval from the phone.

This is not a chatbot project. This is an iOS-first private Agent OS.

CURRENT ARCHITECTURE
- Windows Desktop 24/7 host: D:\ai-council.
- Telegram is still the reliable fallback UI.
- iMessage outbound is live through a Mac Messages.app bridge and launchd.
- iMessage inbound is scaffolded/gated behind Full Disk Access and anti-loop safety.
- Shortcuts endpoint exists as the immediate iPhone capture layer.
- /setup exists and shows live onboarding.
- Grok via xAI API is the research operator.
- Claude Opus 4.8 is planner/council/auditor.
- Codex/Codex worker implements scoped patches and tests.
- Risk Officer R0-R4, approvals, artifacts, memory, brief, reminders, and GitHub are already in the system.

RESEARCH FACTS TO HONOR
- Shortcuts personal automation supports event/time/location/app-open/communication/transaction/settings triggers.
- Shortcuts URL scheme can run a named shortcut with text or clipboard input.
- Shortcuts can receive Share Sheet / What's On Screen input from supported apps.
- Action Button on supported iPhones can run a shortcut.
- App Intents is the long-term native iOS layer for Siri, Spotlight, Shortcuts, widgets, controls, Action Button, Apple Intelligence, Focus, and Live Activities.
- Public iMessage write/read is not a normal iOS app API. For our private system, use the Mac bridge with strict allowlist/audit; public Apple Messages for Business is a later/business path.

DO NOT
- Do not say "done" from scaffolding.
- Do not start new daemons, edit secrets, deploy, restart production, enable Full Disk Access-dependent readers, or send/provider-write without explicit approval.
- Do not bypass Apple platform security.
- Do not send secrets to models.
- Do not produce long generic roadmaps without selecting the next shippable patch.

OPERATING LOOP FOR EVERY ROUND
1. Orient: read current repo state, latest docs/implementation L4.83-L4.91, docs/GOAL_POKE_PLUS_MASTER.md, docs/POKE_CLONE_TARGET.md, and current git status. Preserve user/other-agent dirty changes.
2. Research: use Grok/xAI and web/offical Apple docs for current iOS/Poke/agent patterns. Save a source-backed research note if anything changed.
3. Map surfaces: maintain an iOS Surface Map with each capability:
   - user input source,
   - transport,
   - server endpoint/command,
   - required permission,
   - risk level,
   - implementation status,
   - iPhone smoke test.
4. Plan: run a Claude internal council/tournament:
   - iOS UX lead,
   - Apple platform engineer,
   - OpenClaw/Hermes execution architect,
   - Safety/Risk Officer,
   - Reliability/cost critic.
   Output one winning next patch, not five vague options.
5. Implement: for small safe patches, code directly; for bigger ones, create a Codex worker pack and have Codex implement. Always keep changes surgical.
6. Verify: py_compile, focused tests, full tests. If deploy is approved, Windows tests and live iPhone smoke.
7. Report: changed files, test results, what iPhone capability improved, exact next user action if needed.

IOS SURFACE MAP TO BUILD TOWARD

Layer A — Immediate private iPhone ingress (Shortcuts first)
- Ask Council: text prompt -> /shortcut -> route_message -> Telegram/iMessage response.
- Voice note -> STT -> route_message.
- Screenshot/photo -> vision/OCR -> route_message.
- URL/share sheet -> research brief.
- Clipboard -> task/research/memory.
- "What's On Screen" -> task/research.
- Action Button -> Ask Council or Voice -> task.
- Back Tap -> Ask Council / capture screen.
- Siri phrase -> run Shortcut.
- Apple Watch Shortcut -> quick voice/task.

Layer B — iMessage as Poke-like channel
- Outbound assistant -> Bartek is already live.
- Inbound Bartek -> assistant needs Full Disk Access, cursor, attributedBody decoder, anti-loop, self-thread filtering, and explicit enable.
- All iMessage bodies must be allowlisted to Bartek only, audited, and deduped.
- Approval/cancel/status from iMessage must be safe and cannot bypass Telegram approval rules unless explicitly approved.

Layer C — iOS approval and task control
- Approve/cancel/status buttons or shortcut payloads.
- No R3/R4 action executes from shortcut/iMessage without confirm token and audit.
- iPhone should show "decision, facts, risk, next action".

Layer D — Native iOS app / App Intents path
- If Shortcuts/Mac bridge is stable, design a minimal Swift app:
  - App Intents: Ask Council, Capture URL, Capture Screenshot/Photo, Start Research, Show Status, Approve/Cancel.
  - App Entities: Task, Fact, Reminder, Artifact, Source, Action.
  - Widgets: Today status, pending approvals, next action.
  - Live Activities: long-running task progress.
  - Push notifications/APNs: proactive alerts independent of Telegram.
  - Spotlight/Siri/App Shortcuts: natural invocation.
  - Share Extension: robust share sheet capture.
  - Control Center / Action Button control if appropriate.
  - Strict auth token/device allowlist.

Layer E — Integrations from iPhone intent
- Gmail/Calendar/Drive/GitHub now; Notion/Linear/Slack/WhatsApp/SMS later.
- Read-only first; write only behind Risk Officer and approval.
- iPhone UX must expose what happened and what is waiting for approval.

DELIVERABLES FOR THIS ROUND
1. Audit current L4.83-L4.91 state and list exactly what is live, scaffolded, gated, and missing.
2. Create or update docs/architecture/IOS_SURFACE_MAP.md.
3. Create a sprint plan named "L4.92 iOS Command Center" or choose a better name if evidence says another patch is higher value.
4. Implement the first shippable iOS-focused improvement unless blocked by user-only permission.
5. If blocked by Full Disk Access/OAuth/device choice, convert the blocker into a phone-visible setup card and one exact user action.

ACCEPTANCE CRITERIA
- From iPhone, Bartek can see one setup/status answer that explains current iOS readiness.
- Every iOS input path has a status: live, gated, missing, or planned.
- No hidden permission is required without being surfaced in /setup or /ios.
- No external write or daemon start happens without approval.
- Tests prove routes and gates.
- The next action is one concrete thing, not a vague roadmap.

CURRENT BEST NEXT PATCH CANDIDATE
L4.92: /ios command + iOS Surface Map + iPhone Command Center.
It should show:
- Telegram status,
- iMessage outbound/inbound status,
- Shortcuts token/endpoint status,
- Action Button/Back Tap/Share Sheet recipe pack status,
- Full Disk Access requirement,
- Google/GitHub integration readiness,
- pending approvals,
- one best next action.

After L4.92, likely L4.93 is either:
- enable and smoke-test iMessage inbound after Bartek grants Full Disk Access,
or
- package iOS Shortcuts recipes into importable/shareable shortcut specs,
or
- design the minimal Swift App Intents app if Shortcuts+iMessage are stable.

Final rule: judge every change by this question:
"Does this make Bartek's iPhone feel more like one powerful private AI operator that can actually use his world?"
```

## Suggested First Sprint

L4.92 should probably be `/ios` as the phone command center. `/setup` is broad onboarding; `/ios` should be specifically about iPhone readiness and deep integration.

Minimum `/ios` sections:

- Channels: Telegram, iMessage outbound, iMessage inbound, Mac bridge launchd.
- Capture: Shortcuts endpoint, Ask Council, Voice, Screenshot, URL, Share Sheet, What's On Screen, Action Button, Back Tap, Watch.
- Control: status, details, facts, next, approvals, cancel, reminders.
- Native-app path: App Intents / Widgets / Live Activities / Push / Share Extension status.
- Permissions: Tailscale, token, Full Disk Access, macOS Automation, Google OAuth.
- One best next action.

Do not build a Swift app before proving the no-app Shortcuts + iMessage path is fully useful. The native app becomes worth it when:

- Shortcuts UX becomes too manual,
- approval cards need better mobile UI,
- APNs/push is needed,
- widgets/Live Activities would materially reduce friction,
- App Intents/Siri/Spotlight become the shortest path to "always available".

