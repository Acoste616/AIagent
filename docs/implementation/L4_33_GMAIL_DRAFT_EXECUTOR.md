# L4.33 Gmail Draft Executor v0

## Purpose

L4.33 expands the provider executor beyond GitHub. The new operation is Gmail draft creation only. It does not send email.

This moves the system closer to Poke-like operator behavior: a Telegram conversation can become a real provider-side object, while still preserving approval, explicit confirmation, evidence artifacts, and verifier checks.

## Supported Operation

- Connector: `gmail`
- Provider operation: `gmail.users.drafts.create`
- API contract: `POST https://gmail.googleapis.com/gmail/v1/users/me/drafts`
- Payload: `message.raw`, a base64url encoded RFC 2822 MIME message
- Required Google scope: `https://www.googleapis.com/auth/gmail.compose`
- Source: official Gmail API docs, `https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/create`

## Required Gates

No Gmail provider write occurs unless all of these are true:

- `/provider request <integration_action_id>` created a provider write request.
- `/approve <request_id>` approved the write request checkpoint.
- `/provider execute <request_id> <confirm_token>` includes the stored confirm token.
- `AI_COUNCIL_PROVIDER_WRITE_ENABLED=true`
- `AI_COUNCIL_GMAIL_DRAFT_WRITE_ENABLED=true`
- Google OAuth is configured.
- Gmail draft fields are valid:
  - recipient exists and looks like an email address,
  - subject exists,
  - subject has no newline and is at most 998 characters,
  - body is at most 100,000 characters.

If any gate fails, the system writes a local `provider_write_dry_run` artifact and reports:

```text
external_write_performed: false
```

## Artifacts

For a blocked execution:

- `artifacts/provider-write-requests/<request_id>/provider_write_dry_run.json`
- `artifacts/provider-write-requests/<request_id>/provider_write_dry_run.md`

For a successful Gmail draft creation:

- `artifacts/provider-write-requests/<request_id>/provider_write_result.json`
- `artifacts/provider-write-requests/<request_id>/provider_write_result.md`

The provider result stores:

- source action id,
- connector and provider operation,
- MIME request payload metadata,
- Gmail draft id,
- Gmail message id,
- Gmail thread id if returned,
- `external_write_performed=true`.

## Verification

`/provider verify <request_id>` verifies:

- result artifact path is under `artifacts`,
- action id matches,
- connector is supported,
- provider operation matches the connector,
- provider reference exists,
- `external_write_performed=true` is present in both action payload and artifact.

Failure artifacts with `provider_write_failed` are not marked verified. The same request id cannot be retried after a provider POST result because the POST may have reached Gmail even when the client saw a network/API error.

## What Is Still Missing

This is still not full Poke parity.

L4.34 should add one of:

- Calendar event create with the same approval/confirm/verifier model, or
- provider dedupe/read-before-write for GitHub and Gmail.

The system still needs deeper proactive recipes, stronger source-backed memory, iPhone Shortcut hardening, Calendar/Drive write adapters, and eventually a private Messages/iMessage bridge.
