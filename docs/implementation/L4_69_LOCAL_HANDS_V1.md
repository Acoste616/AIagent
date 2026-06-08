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

## L4.69.1 — sandboxed WRITE (LANDED, off by default)

Adds `/fs write <file> = <content>` (dry-run preview) → `/fs commit <file> = <content>` (executes) → `/fs undo <file>` (rollback). Gated by **both** `AI_COUNCIL_LOCAL_HANDS` AND `AI_COUNCIL_LOCAL_HANDS_WRITE` (both default false). Reuses the hardened `safe_resolve`; target written with **`O_NOFOLLOW`** (atomic no-follow on POSIX).

### Write-path red-team (3 agents) — confirmed issues, all FIXED
- **CRITICAL — symlinked-backup escape:** the original backup path `<file>.hands-bak` (via `with_name`) was unvalidated; a planted sandbox symlink redirected the backup write OUTSIDE root (reproduced). **Fix:** backups moved OUT of the sandbox to `STATE_DIR/hands_backups` (keyed by target hash, with a provenance `.meta`), so no sandbox-controlled name can redirect them; target write uses `O_NOFOLLOW`.
- **HIGH — sibling clobber:** a real file named `x.hands-bak` was silently overwritten. **Fixed** (no in-sandbox backup files anymore).
- **HIGH — sentinel clobber:** `x.hands-bak-absent` as real data → undo deleted the file. **Fixed** (no in-sandbox sentinel; existence tracked in the out-of-sandbox `.meta`).
- **MEDIUM — wrong/stale restore:** **mitigated** via `.meta` provenance (undo refuses if `meta.target` ≠ resolved target).
- **MEDIUM — parent-swap TOCTOU:** mitigated by the pre-write reparse re-check + `O_NOFOLLOW`; residual on Windows (no `O_NOFOLLOW`) is documented (single-user box).
- **write-to-root:** already safe (rejected as not-a-regular-file).

Tests: `HandsWriteTests` (9) incl. `test_backup_symlink_vector_closed`, `test_sibling_hands_bak_file_not_clobbered`, preview/commit/undo cycle, escape-never-touches-outside, symlink-write rejected, off-by-default, size limit. Suite: **353 passed**.

### Enabling write (gated)
Set BOTH `AI_COUNCIL_LOCAL_HANDS=true` and `AI_COUNCIL_LOCAL_HANDS_WRITE=true`, restart. Until then `/fs write` returns "wyłączony".

## Follow-up (NOT here)
Full fd-based `O_NOFOLLOW` on Windows (native API) to close the residual parent-swap TOCTOU for multi-user; multi-level undo history; append mode.
