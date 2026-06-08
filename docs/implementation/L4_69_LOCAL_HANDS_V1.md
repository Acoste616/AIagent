# L4.69 — OpenClaw Hands v1 (safe read-only local filesystem)

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Red-team: 5-agent adversarial workflow
Status: LANDED + tested (344 passed). **OFF by default** (`AI_COUNCIL_LOCAL_HANDS`).

## What
The first real "ręce jak OpenClaw" — the agent can now **see** the local filesystem, safely. Read-only commands bounded to ONE sandbox root:
- `/fs list [path]` · `/fs read <file>` · `/fs stat <path>`
- Sandbox root: `AI_COUNCIL_HANDS_ROOT` (default `workspaces/hands`), created + `resolve(strict=True)` at init.
- No write/delete/move/exec, no network. Every op is R0 + audited. Not in `LLM_ROUTER_ALLOWED_COMMANDS` (explicit-only).

## Security model (the whole point)
`safe_resolve(rel)` is the boundary. Hardened after the red-team:
1. **NFKC-normalize** the input first — folds homoglyph slashes (U+FF0F) and dot-leaders (U+2024) into real `/` and `.` so the string checks see what the OS will.
2. Reject **backslash**, **colon** (NTFS ADS + drive-relative), leading `/` or `~`, and any **control/format/surrogate** char (`Cc/Cf/Cs`, ord<0x20, 0x7F).
3. Per component reject: `..`, **trailing dot/space** (Windows strips these → `.. `→`..` escape), and **reserved DOS device names** (`CON/PRN/AUX/NUL/COM1-9/LPT1-9/CONIN$/...`, stem before first dot, case-insensitive).
4. Length + depth guards.
5. `resolve(strict=False)` then **`is_relative_to(root)`**.
6. **Reparse-point walk**: reject if any component is a symlink OR Windows **junction/mountpoint** (`is_symlink()` misses junctions → also check `st_reparse_tag`).
7. **`realpath` canonical re-check** (follows anything the walk missed).
8. `fs_read` adds a **TOCTOU re-check** (reparse + canonical containment) right before reading.
Read guards: max 1 MiB, binary detection (NUL in first 4096B → `[binary omitted]`), and a **prompt-injection fence** (file content wrapped in `<file>`, with `</file>` / triple-backtick / `<|` escaped) so file bytes can never break out into instructions.

## Red-team (5 adversarial agents, distinct lenses)
Workflow `hands-sandbox-redteam`. Confirmed escapes found in the FIRST implementation and **fixed**:
- **Reserved device names** (`NUL`,`CON`,`COM1`,`CONIN$`) — passed all checks, Windows opens the device (outside sandbox). → reserved-name reject.
- **Trailing-space dot-dot** (`.. /outside`) — `!= ".."` so missed; Windows strips space → parent. → trailing-dot/space reject + NFKC.
- **NTFS ADS colon** (`a.txt:secret`, `..:$DATA`) — interior colon allowed. → reject any colon.
- **TOCTOU** final/intermediate swap to symlink/junction after the check. → reparse walk + read-time re-check.
- **Unicode homoglyphs** (fullwidth solidus, one-dot leader). → NFKC normalize first.
All now covered by `HandsSandboxTests` (13 tests). Verified: 13 attack vectors incl. all confirmed escapes → **zero leak**.

## Verification
- `pytest -q tests/test_ai_council.py` — **344 passed**; `py_compile` clean; ledger md5 unchanged.

## Enabling (gated — host decision)
Set `AI_COUNCIL_LOCAL_HANDS=true` (+ optional `AI_COUNCIL_HANDS_ROOT`) on the host and restart. Until then `/fs` returns "wyłączone". Recommended first use: a throwaway folder under `workspaces/hands`.

## Follow-up (NOT here)
L4.69.1 write ops (create/append) behind R3 approval + dry-run + verify + rollback (inverse-op log). v1 proves the read-only jail is airtight first. Residual: full fd-based O_NOFOLLOW TOCTOU elimination (current re-check is strong for a single-user box; note for multi-user).
