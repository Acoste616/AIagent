# AI Council L3.1 Telegram Media Capture Implementation

Date: 2026-06-06
Target runtime: `D:\ai-council` on Windows Desktop

## Outcome

L3.1 adds the first iPhone/Poke-like capture path without starting a new daemon
or bridge. The existing Telegram bot now accepts voice notes, photos/screenshots,
documents, audio, and video messages from the allowlisted user, downloads the
Telegram file, stores it as a local task artifact, and returns a normal AI
Council summary with `/details`.

## Implemented

- Telegram media detection:
  - `voice`
  - `audio`
  - `photo`
  - `document`
  - `video`
- Largest-photo selection for screenshot/photo messages.
- Telegram `getFile` lookup.
- Telegram file download into:
  - `D:\ai-council\artifacts\<task_id>\media\...`
- `media.json` metadata per capture task.
- `/capture` internal command marker.
- Listener no longer ignores allowlisted non-text messages when media exists.
- L3.1 capabilities/status labels.

## Verification

Local repository:

```text
Ran 50 tests
OK
```

Windows Desktop:

```text
Ran 50 tests
OK
```

Windows status after deployment:

```text
Bartek AI Council Telegram: Running
running_tasks: 0
stuck_tasks: 0
codex: OK
claude: OK
claude_flow: OK model=claude-opus-4-8 mode=plan
grok: OK
```

Smoke checks:

```text
Capabilities L3.1 active
voice
```

Synthetic Windows capture:

```text
[AI Council] task-...
report_exists=True
media_exists=True
```

## Boundaries

L3.1 captures and stores media, but it does not yet transcribe voice, OCR
screenshots, inspect document contents, or run multimodal analysis. Those are
the next layer after this capture path is stable.

No shell execution, external write, iMessage bridge, Apple Messages bridge, or
iOS Shortcut daemon was introduced.
