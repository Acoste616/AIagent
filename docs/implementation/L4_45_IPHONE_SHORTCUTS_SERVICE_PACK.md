# L4.45 iPhone Shortcuts Service Pack

L4.45 turns the existing Shortcuts HTTP ingress into an operable Windows service pack without starting a new daemon automatically.

## What Changed

- `/shortcuts` now reports `iPhone Shortcuts L4.45`.
- `/shortcuts` shows token state, endpoint, bind scope, payload examples, recent Shortcuts tasks, and Windows launcher paths.
- Shortcuts HTTP `/health` returns the service version.
- `/health`, `/selftest`, `/goal`, `/capabilities`, and Poke Gap expose the Shortcuts service pack.
- Windows deploy now includes:
  - `windows-deploy/start-ai-council-shortcuts.ps1`
  - `windows-deploy/status-ai-council-shortcuts.ps1`
  - `windows-deploy/stop-ai-council-shortcuts.ps1`

## Safety

- The Shortcuts listener is not started by default.
- `AI_COUNCIL_SHORTCUT_TOKEN` is required before the listener starts.
- Token values are never printed in `/shortcuts` or status output.
- Shortcuts can capture, read, research, and check status.
- Approval, deny, cancel, external writes, publishing, contacts, billing, auth, and destructive actions stay blocked behind Telegram approval paths.

## Activation

After approval, on Windows:

```powershell
cd D:\ai-council\windows-deploy
powershell -ExecutionPolicy Bypass -File .\start-ai-council-shortcuts.ps1
```

Status:

```powershell
powershell -ExecutionPolicy Bypass -File .\status-ai-council-shortcuts.ps1
```

Stop:

```powershell
powershell -ExecutionPolicy Bypass -File .\stop-ai-council-shortcuts.ps1
```

## iPhone Payloads

Ask Council:

```json
{"text":"co mam teraz zrobić?"}
```

Share URL to research:

```json
{"url":"https://example.com","title":"source","mode":"url"}
```

Voice, screenshot, or file:

```json
{"media_base64":"...","filename":"screenshot.png","mime_type":"image/png","caption":"sprawdź to"}
```

Read-only control:

```json
{"action":"agent"}
```

## Verification

- `python3 -m py_compile ai_council.py`
- `python3 -m pytest tests/test_ai_council.py -q`
- `python3 ai_council.py respond "/shortcuts"`
- Windows status script reports stopped unless the listener was explicitly started.
