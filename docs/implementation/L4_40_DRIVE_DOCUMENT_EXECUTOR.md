# L4.40 Drive Document Executor

## Decision

L4.40 adds the fourth gated provider executor: Google Drive document creation.
It follows the same AI Council write model as GitHub issues, Gmail drafts, and
Calendar events:

- integration draft,
- local execution pack,
- provider manifest,
- separate provider write request,
- explicit `/approve`,
- confirm token,
- provider-specific env gate,
- provider result artifact,
- `/provider verify`.

## What Changed

- `drive.files.create` is now included in provider executor operations.
- New gate: `AI_COUNCIL_DRIVE_FILE_WRITE_ENABLED=true`.
- Drive execution also requires:
  - `AI_COUNCIL_PROVIDER_WRITE_ENABLED=true`,
  - Google OAuth config,
  - `/provider request`,
  - `/approve <request_id>`,
  - `/provider execute <request_id> <confirm_token>`.
- The executor creates a Google Docs document through Drive multipart upload:
  - metadata `mimeType: application/vnd.google-apps.document`,
  - media body as UTF-8 plain text,
  - optional `folder_id` as Drive parent.
- Provider result artifacts capture the Drive `id`, `name`, `mimeType`, and
  `webViewLink`.

## Safety

- No Drive write can happen when the global provider gate or Drive-specific gate
  is disabled.
- The executor validates title/name, body/outline presence, body size, outline
  size, MIME type, and optional folder ID before network calls.
- L4.38 dedupe still blocks duplicate Drive provider writes before request
  creation and before execution.
- Failed provider writes are not retried automatically and require manual check.

## Verification

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m pytest tests/test_ai_council.py -q -k "drive_provider_write or provider_write_dedupe or github_provider_write_request_executes"`
- Full local test suite: `217 passed`

## Sources

- Google Drive API upload guide: <https://developers.google.com/drive/api/v3/manage-uploads>
- Google Drive API `files.create`: <https://developers.google.com/drive/api/reference/rest/v3/files/create>
