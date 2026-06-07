# L4.38 Provider Write Dedupe

## Decision

L4.38 adds a provider write dedupe/idempotency guard before expanding external
write integrations. This prevents two approved provider requests with the same
connector, operation, and canonical request body from creating duplicate external
objects.

## What Changed

- Provider write request payloads now include:
  - `dedupe_key` (SHA-256 over connector, operation, and canonical request body)
  - `dedupe_scope: connector+provider_operation+canonical_request_body`
- `/provider request <integration_action_id>` blocks duplicate active requests
  before creating a second pending action.
- `/provider execute <request_id> <confirm>` checks dedupe again immediately
  before provider network calls.
- Legacy/pre-L4.38 duplicate requests without `dedupe_key` are still detected by
  recomputing the key from connector, operation, and request body.
- Dedupe blocks write execution with a dry-run artifact and
  `external_write_performed=false`.
- Terminal blocked statuses (`write_blocked`, `verify_failed`, denied,
  dismissed, cancelled, editing) do not create permanent dedupe conflicts. A
  failed or blocked attempt can be retried with a fresh request.

## Safety

- No new provider write capability is added.
- No shell execution is added.
- Existing GitHub/Gmail/Calendar provider gates remain unchanged.
- Drive remains blocked until a dedicated executor is implemented.
- Dedupe is not a substitute for provider-specific read-before-write; it is the
  shared precondition before adding broader external writes.

## Verification

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m pytest tests/test_ai_council.py -q -k "provider_write_dedupe or github_provider_write_request_executes"`
- Full local test suite: `215 passed`
