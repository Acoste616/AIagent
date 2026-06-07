# L4.50 Poke Front Quality Guard

## Goal

L4.50 makes Poke-style response quality observable.

The Telegram bot may be online and still feel wrong if it leaks debug output,
raw operator labels, Windows process noise, or very long capability dumps. This
guard records those failures as `front_quality` warnings so the autonomous
error loop, Grok research pack, Claude planning pass, and host Codex audit can
work from concrete examples.

## Behavior

The guard runs only for real Telegram sends and only for user-facing routes.
Technical commands such as `/health`, `/selftest`, `/status`, `/details`,
`/errors`, `/recipes`, `/connector`, and provider/admin commands are skipped.

Detected issues:

- `debug_metadata`: leaked `route=` or `audit_log=` lines.
- `windows_process_noise`: leaked `SUCCESS/INFO/ERROR: The process with PID`.
- `raw_operator_label`: raw `[Codex]`, `[Claude]`, or `[Grok]` label reached the front.
- `raw_runtime_detail`: traceback, subprocess, cwd/env, or sandbox detail reached a user-facing response.
- `too_long`: response exceeds `AI_COUNCIL_FRONT_QUALITY_MAX_CHARS`.
- `command_spam`: response prints too many command-only lines.
- `empty_response`: response body is empty.

Normal short `[Council]` responses are allowed.

Long informational commands such as `/goal`, `/capabilities`, `/front`,
`/agent`, `/followups`, and `/nudges` are exempt from `too_long` and
`command_spam`, but still trigger on leaked debug metadata, raw operator labels,
runtime details, and Windows process noise.

## Commands And Signals

- `/front` shows `front_quality_24h` and latest issue.
- `/health` exposes `front_quality=L4.50`.
- `/errors` shows stored `front_quality` warnings.

Config:

```env
AI_COUNCIL_FRONT_QUALITY_GUARD=true
AI_COUNCIL_FRONT_QUALITY_MAX_CHARS=2400
AI_COUNCIL_FRONT_QUALITY_MAX_COMMAND_LINES=6
```

## Safety

This release does not rewrite outgoing responses. It only logs quality warnings.
That keeps the first iteration low-risk and gives the later Grok -> Claude ->
Codex loop examples to fix.

## Verification

Local:

```bash
python3 -m py_compile ai_council.py
python3 -m pytest tests/test_ai_council.py -q -k "front_quality or front_reliability or true_poke_target"
python3 -m pytest tests/test_ai_council.py -q
```

Windows after deploy:

```powershell
py -3 D:\ai-council\ai_council.py respond "/front"
py -3 D:\ai-council\ai_council.py respond "/health"
```

Expected:

- `/front` includes `front_quality_24h`.
- `/health` includes `front_quality=L4.50`.
