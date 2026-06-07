# L4.34 Calendar Event Executor v0

## Purpose

L4.34 expands provider execution to Google Calendar event creation. The operation is intentionally narrow: create an event in the configured calendar after approval and confirmation.

The executor uses `sendUpdates=none`, so it does not send attendee notifications or invitations in this layer.

## Supported Operation

- Connector: `calendar`
- Provider operation: `calendar.events.insert`
- API contract: `POST https://www.googleapis.com/calendar/v3/calendars/{calendarId}/events`
- Query policy: `sendUpdates=none`
- Required Google scope: `https://www.googleapis.com/auth/calendar.events`
- Source: official Google Calendar API docs, `https://developers.google.com/workspace/calendar/api/v3/reference/events/insert`

## Required Gates

No Calendar provider write occurs unless all of these are true:

- `/provider request <integration_action_id>` created a provider write request.
- `/approve <request_id>` approved the write request checkpoint.
- `/provider execute <request_id> <confirm_token>` includes the stored confirm token.
- `AI_COUNCIL_PROVIDER_WRITE_ENABLED=true`
- `AI_COUNCIL_CALENDAR_EVENT_WRITE_ENABLED=true`
- Google OAuth is configured.
- Calendar event fields are valid:
  - summary exists,
  - start exists,
  - end exists,
  - timezone exists,
  - start and end parse as ISO datetimes and end is after start,
  - attendees are optional but must look like email addresses when present,
  - summary and description stay under local size limits.

L4.34 intentionally uses one timezone field for both start and end. Multi-timezone events can be added in a later executor revision.

If any gate fails, the system writes a local `provider_write_dry_run` artifact and reports:

```text
external_write_performed: false
```

## Artifacts

For a blocked execution:

- `artifacts/provider-write-requests/<request_id>/provider_write_dry_run.json`
- `artifacts/provider-write-requests/<request_id>/provider_write_dry_run.md`

For a successful Calendar event creation:

- `artifacts/provider-write-requests/<request_id>/provider_write_result.json`
- `artifacts/provider-write-requests/<request_id>/provider_write_result.md`

The provider result stores:

- source action id,
- connector and provider operation,
- calendar id,
- `sendUpdates=none`,
- Calendar event payload,
- Calendar event id,
- Calendar event html link if returned,
- `external_write_performed=true`.

## Verification

`/provider verify <request_id>` verifies:

- result artifact path is under `artifacts`,
- action id matches,
- connector is supported,
- provider operation matches the connector,
- provider reference exists,
- `external_write_performed=true` is present in both action payload and artifact.

Failure artifacts with `provider_write_failed` are not marked verified. The same request id cannot be retried after a provider POST result because the POST may have reached Calendar even when the client saw a network/API error.

## What Is Still Missing

This is still not full Poke parity.

L4.35 should add one of:

- provider dedupe/read-before-write for GitHub, Gmail, and Calendar,
- Drive document/file create with the same approval/confirm/verifier model.

The system still needs deeper proactive recipes, stronger source-backed memory, iPhone Shortcut hardening, Drive write adapter, and eventually a private Messages/iMessage bridge.
