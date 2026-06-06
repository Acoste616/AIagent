# L4.0 iPhone Shortcuts Ingress Implementation

Date: 2026-06-07

## What Changed

- Added optional `serve-shortcuts` HTTP ingress for iPhone Shortcuts.
- Endpoint supports:
  - text/prompt/query/transcript/note,
  - shared URL/title,
  - base64 media attachment as screenshot/photo/audio/video/document.
- Shortcut text is routed through the same `route_text` pipeline as Telegram.
- Shortcut media is saved under task artifacts, analyzed through the existing media layer, then routed through media-to-intent.
- Results can be returned as JSON and optionally sent to Telegram.
- Token auth is required with:
  - `X-AI-Council-Token: ...`
  - or `Authorization: Bearer ...`

## CLI

```bash
python -X utf8 ai_council.py serve-shortcuts --host 127.0.0.1 --port 8788
```

This command is not wired into the existing scheduled task by default.

## Environment

```env
AI_COUNCIL_SHORTCUT_TOKEN=
AI_COUNCIL_SHORTCUT_HOST=127.0.0.1
AI_COUNCIL_SHORTCUT_PORT=8788
AI_COUNCIL_SHORTCUT_SEND_TELEGRAM=true
AI_COUNCIL_SHORTCUT_MAX_BODY_BYTES=25000000
```

`AI_COUNCIL_SHORTCUT_TOKEN` must be configured before the server starts.

## Example Payloads

Text / URL:

```json
{
  "text": "Zrób research tej strony",
  "url": "https://example.com",
  "send_telegram": true
}
```

Media:

```json
{
  "filename": "screenshot.jpg",
  "mime_type": "image/jpeg",
  "media_base64": "...",
  "caption": "Przeanalizuj i wyciągnij next steps",
  "send_telegram": true
}
```

## Safety

- No listener is enabled automatically.
- No Apple Messages/iMessage bridge is started.
- No external write action is added.
- Existing Risk Officer and side-effect approval rules still apply.
- Token is mandatory for HTTP requests.

## Verification

Local Mac:

- `python3 -X utf8 tests/test_ai_council.py`
- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- Result: `64/64 OK`

Covered tests:

- Shortcut auth requires matching token.
- Shortcut text starts a background task.
- Shortcut media saves artifact, extracts text, routes derived intent.
