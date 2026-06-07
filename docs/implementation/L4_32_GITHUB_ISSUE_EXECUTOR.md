# L4.32 GitHub Issue Executor v0

## Purpose

L4.32 is the first provider executor that can move from a Telegram approval flow to a real external write. The scope is intentionally narrow: GitHub issue creation only.

This closes the biggest L4.31 gap: the system could create provider write requests, but every execution still ended as a local dry-run/blocker. Poke-like behavior needs actual operator execution, but only behind explicit gates and verifiable artifacts.

## Supported Operation

- Connector: `github`
- Provider operation: `github.issues.create`
- API contract: `POST https://api.github.com/repos/{owner}/{repo}/issues`
- Source: official GitHub REST Issues API docs, `https://docs.github.com/en/rest/issues/issues?apiVersion=latest`

The request payload is built from the verified integration draft:

```json
{
  "title": "Issue title",
  "body": "Issue body",
  "labels": ["optional-label"]
}
```

## Required Gates

No external write occurs unless all of these are true:

- `/provider request <integration_action_id>` created a provider write request.
- `/approve <request_id>` approved the write request checkpoint.
- `/provider execute <request_id> <confirm_token>` includes the stored confirm token.
- `AI_COUNCIL_PROVIDER_WRITE_ENABLED=true`
- `AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED=true`
- `GITHUB_TOKEN` or `GH_TOKEN` is configured.
- The request body has a valid `owner/repo` and a non-empty title.
- The title is at most 256 characters and body is at most 65,536 characters.

If any gate fails, the system writes a local `provider_write_dry_run` artifact and reports:

```text
external_write_performed: false
```

## Artifacts

For a blocked execution:

- `artifacts/provider-write-requests/<request_id>/provider_write_dry_run.json`
- `artifacts/provider-write-requests/<request_id>/provider_write_dry_run.md`

For a successful GitHub issue creation:

- `artifacts/provider-write-requests/<request_id>/provider_write_result.json`
- `artifacts/provider-write-requests/<request_id>/provider_write_result.md`

The provider result stores:

- source action id,
- connector and provider operation,
- request payload,
- GitHub response,
- `html_url`,
- provider id/number,
- `external_write_performed=true`.

## Verification

`/provider verify <request_id>` now supports two evidence types:

- Dry-run evidence: verifies blocked write artifacts and `external_write_performed=false`.
- Provider result evidence: verifies result artifact path, action id, GitHub connector, `github.issues.create`, provider reference, and `external_write_performed=true`.

## What Is Still Missing

This is not full Poke parity yet.

L4.33 expands the same approval/confirm/verifier model to Gmail draft create.

L4.33 should also add client-side dedupe/read-before-write for GitHub, because GitHub's create issue endpoint does not provide a native idempotency key. L4.32 blocks retry on the same request id, but two separate approved write requests can still create duplicate issues.

After that, the system still needs Calendar/Drive write adapters, deeper proactive recipes, richer memory retrieval, better long-task UX, iPhone Shortcuts hardening, provider dedupe/read-before-write, and eventually a private Messages/iMessage bridge.
