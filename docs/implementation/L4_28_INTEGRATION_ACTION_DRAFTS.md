# L4.28 Integration Action Drafts

Date: 2026-06-07

## Problem

The system could read Gmail, Calendar, Drive, and GitHub context, but write-capable integrations were still represented as generic approval proposals. That made the bot feel less like a capable operator: it could say that an action needed approval, but it did not prepare a concrete reviewable draft.

## Implemented

- Added integration draft actions for:
  - Gmail email drafts,
  - Calendar event drafts,
  - Drive/Docs document drafts,
  - GitHub issue/PR drafts.
- Added `/connector draft <gmail|calendar|drive|github> <intent>`.
- Added `/drafts` and `/drafts show <action_id>`.
- Action Planner now converts integration side-effect requests such as email/schedule/github/drive writes into `integration_draft` pending actions instead of generic `planner_proposal` actions.
- `/agent` surfaces these drafts through the existing pending action inbox.
- `approve` for `integration_draft` records an approval checkpoint only.
- `/execute` remains blocked for R3/R4, so this layer does not send email, create events, write Drive files, publish GitHub issues, or perform external API writes.
- `action_id` generation now includes a unique seed to avoid same-second collisions.

## Safety

- Draft creation is local state only.
- Draft payloads explicitly include `external_write: false`.
- Missing fields are recorded so the user can review recipient/time/repo/title before any future adapter exists.
- Approval records the decision and audit trail, but execution adapters are intentionally not implemented in this layer.

## Verification

- Mac tests: `178/178 OK`.
- Syntax check: `python3 -m py_compile ai_council.py tests/test_ai_council.py`.
- Claude review completed; risk reason, `/drafts show`, list filtering, connector matching, signature, and GitHub repo default were tightened before Windows deployment.
- Windows Desktop tests: `178 passed, 107 subtests passed`.
- Windows Desktop syntax check: `python -m py_compile ai_council.py tests\test_ai_council.py`.
- Windows Desktop smoke: `dry-route /drafts`, natural `draft gmail ...`, `/selftest`, and `doctor` all OK after listener restart.

## Remaining Gap

L4.28 prepares concrete integration actions. It still does not execute them. The next layer is L4.29 Integration Execution Adapters: separate adapters with hard approval gates, dry-run previews, source-backed verification, and per-connector rollback/undo semantics where available.
