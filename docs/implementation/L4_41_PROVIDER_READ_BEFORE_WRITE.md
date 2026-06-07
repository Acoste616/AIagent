# L4.41 Provider Read-Before-Write

L4.41 adds provider-specific read-before-write checks before any approved external write.

The goal is simple: after approval and confirm token, the system still checks the target provider for an existing matching object before it sends a POST/upload. If the provider read finds a duplicate or the provider read fails, AI Council writes a local dry-run artifact and does not perform the external write.

## Provider Checks

- GitHub issue write calls GitHub issue search first with `repo:<owner>/<repo> is:issue in:title "<title>"`, then blocks on exact title match.
- Gmail draft write calls `users.drafts.list` with a Gmail query, then `users.drafts.get` for candidate headers, then blocks on exact subject plus matching recipient.
- Calendar event write calls `events.list` inside the requested time window with the event summary, then blocks on exact summary/start/end match.
- Drive document write calls `files.list` with `name`, Google Docs mime type, `trashed=false`, and optional parent folder, then blocks on exact document name.

## Safety Contract

- No read-before-write pass means no external write.
- Conflict status becomes `write_blocked`.
- Failed provider reads become `write_blocked`, not `provider_write_failed`, because no POST/upload happened.
- Every block writes `provider_write_dry_run.json` and `provider_write_dry_run.md`.
- Every successful write result includes `provider_read_before_write` in `provider_write_result.json`.
- The feature defaults on and can be disabled only with `AI_COUNCIL_PROVIDER_READ_BEFORE_WRITE_ENABLED=false`.

## Known Limits

- Gmail list preflight searches by the first recipient plus subject, then validates that at least one intended recipient appears in the candidate draft headers. This is conservative for common one-recipient drafts; multi-recipient false negatives remain possible if Gmail search does not return a candidate draft.
- GitHub search rate limits can make preflight return `failed`; that intentionally blocks the write until the request can be checked again.
- GitHub issue search can be eventually consistent. Local L4.38 dedupe still catches duplicate requests created through AI Council, but very fresh external issues may not appear in provider search immediately.
- Provider reads are bounded to small result pages: GitHub `per_page=20`, Gmail/Calendar/Drive `maxResults` or `pageSize=20`. Exact duplicate matches beyond those windows can still be missed.
- Drive folder-specific preflight checks the first configured parent folder. Current Drive document drafts normally use zero or one folder.

## Source APIs

- GitHub issue search uses GitHub issue/pull request search qualifiers: `is:issue`, `in:title`, and `repo:OWNER/REPO`.
  Source: https://docs.github.com/search-github/searching-on-github/searching-issues-and-pull-requests
- Gmail draft preflight uses `users.drafts.list` and `users.drafts.get`.
  Sources: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/list and https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/get
- Calendar event preflight uses `events.list`.
  Source: https://developers.google.com/workspace/calendar/api/v3/reference/events/list
- Drive document preflight uses `files.list`.
  Source: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list

## Verification

Local targeted tests cover:

- clear preflight followed by GitHub/Gmail/Calendar/Drive write,
- GitHub duplicate issue blocks before POST,
- Gmail duplicate draft blocks before POST,
- Calendar duplicate event blocks before POST,
- Drive duplicate document blocks before upload,
- provider read failure blocks before POST/upload,
- disabling `AI_COUNCIL_PROVIDER_READ_BEFORE_WRITE_ENABLED` skips preflight and still persists `status=skipped`,
- provider read failures and provider write failures remain distinct.

Full local verification:

```bash
python3 -m py_compile ai_council.py tests/test_ai_council.py
python3 -m pytest tests/test_ai_council.py -q
```
