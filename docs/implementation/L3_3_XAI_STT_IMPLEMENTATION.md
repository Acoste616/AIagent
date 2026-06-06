# AI Council L3.3 xAI STT Implementation

Date: 2026-06-07
Target runtime: `D:\ai-council` on Windows Desktop

## Outcome

L3.3 upgrades Telegram voice/audio/video capture from `transcription_pending`
to real speech-to-text through xAI STT REST. The implementation uses only Python
stdlib multipart upload, so the Windows service does not require `websockets`,
`websocket-client`, or `ffmpeg`.

## Official API Basis

- xAI Speech to Text: `https://docs.x.ai/developers/model-capabilities/audio/speech-to-text`
- xAI API reference for STT: `POST https://api.x.ai/v1/stt`

The REST path accepts a multipart `file` upload and supports common audio
formats including Telegram-compatible OGG/Opus. The `file` field must be sent
after metadata fields.

## Implemented

- `request_multipart_json` using stdlib `urllib`.
- `xai_stt_transcribe` for voice/audio/video media.
- Config:
  - `AI_COUNCIL_STT_URL`
  - `AI_COUNCIL_STT_LANGUAGE`
  - `AI_COUNCIL_STT_FORMAT`
  - `AI_COUNCIL_STT_KEYTERMS`
  - `AI_COUNCIL_STT_MAX_BYTES`
  - `AI_COUNCIL_STT_MAX_CHARS`
- Analysis statuses:
  - `transcribed`
  - `transcription_unavailable`
  - `transcription_failed`
  - `transcription_blocked`
- L3.3 capabilities/status labels.

## Verification

Local repository:

```text
Ran 56 tests
OK
```

Windows Desktop:

```text
Ran 56 tests
OK
```

Windows smoke check with mocked STT response:

```text
Capabilities L3.3 active
transcribed
Transkrypt testowy.
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

## Boundaries

Tests and smoke checks do not burn real xAI STT calls. The deployed path is live
and will call xAI STT when Bartek sends a real voice/audio/video message to the
Telegram bot.

This layer does not add shell execution, Apple Messages/iMessage bridge, public
Apple Messages for Business, iOS Shortcuts daemon, external writes, publishing,
or contact/money/DNS/auth/billing actions.
