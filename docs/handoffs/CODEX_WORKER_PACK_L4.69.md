# Codex Worker Pack — L4.69 OpenClaw Hands v1 (read-only / dry-run local FS)

Prepared by: Claude Opus 4.8 · For: Codex 5.3 Spark worker · Audit: host Codex + Claude review · Date: 2026-06-08
Research: bounded live-Grok call on safe local-execution sandboxing (patterns baked into §3). Depends on: L4.64 (risk classifier hardened).
Goal alignment: this is the first real **"ręce jak OpenClaw"** — safe local hands on the Windows desktop. v1 is **read-only**; writes are a later layer behind R3 approval.

You are the implementation worker. This is **security-sensitive** — implement EXACTLY the safety model below, test every guard, off by default. **No writes, no exec, no deploy/push.** Return a diff + `docs/implementation/L4_69_*.md`. Claude reviews the path-safety adversarially before any host use.

## 1. Scope (v1 = read-only, sandboxed)

A `local_fs` capability bounded to ONE sandbox root that can: **list** a directory, **read** a text file (size-capped), **stat** a path. Nothing else. Every op goes through the existing Risk Officer as **R0 (read-only)** and is audit-logged. Disabled unless `AI_COUNCIL_LOCAL_HANDS=true` (default false). NO write/delete/move/exec in v1.

## 2. Anchors (repo)
- Sandbox root: reuse `WORKSPACES_DIR` (line ~56) OR a new `AI_COUNCIL_HANDS_ROOT` (default `WORKSPACES_DIR / "hands"`). MUST be created + `resolve(strict=True)` at init.
- Risk gate: `risk_level_for_text` (7693), `normalize_risk` (7734), `RISK_LEVELS` (105). New ops register as R0; any path that fails a guard → reject (never silently downgrade).
- Audit: `audit(event)` / `append_jsonl` (now locked, L4.64). Command dispatch: follow how existing `/` commands are parsed (`route_text`) and add `/fs` (or extend `/workspace`).
- Risk fence: the L4.64 router fence already blocks destructive prompts; `local_fs` commands must NOT be added to `LLM_ROUTER_ALLOWED_COMMANDS` (keep them explicit-only in v1).

## 3. Safety model (MANDATORY — from Grok research, do not soften)

**Path containment** (the core guard — `safe_resolve(rel) -> Path`):
- Canonical root: `root = Path(cfg_root).resolve(strict=True)`.
- Reject BEFORE resolit if the raw input contains `..`, a backslash `\\`, a drive letter (`[A-Za-z]:`), UNC/extended prefixes (`\\\\`, `\\\\?\\`), or is absolute.
- `p = (root / rel).resolve(strict=False)`; then **assert `p.is_relative_to(root)`** or reject.
- Symlink/junction defense: `os.lstat(p)`; on Windows check `st_reparse_tag` (symlink/junction/mountpoint); if a reparse point, resolve the target and re-apply `is_relative_to(root)`; deny if it escapes. Walk each parent component too (a parent symlink can escape).

**Allowed ops only:** `Path.iterdir` (bounded), `Path.read_text(encoding="utf-8", errors="replace")` (size-capped, text-only), `Path.stat`, `is_file/is_dir`. **Never expose:** `os.walk`, `glob("**")` (no depth limit), `readlink`, `open(...,"rb")` uncapped, `os.popen/system/exec`, any write/delete/rename.

**Limits:** max file 1 MiB (`AI_COUNCIL_HANDS_MAX_BYTES`, reject larger with explicit error; preview = first N bytes only); max dir entries 1024 (abort+error past that); **binary guard**: read first 4096 B, if a `\\0` byte is present return `"[binary omitted]"` instead of content.

**Prompt-injection neutralization:** wrap ALL returned file content in a data fence `<file path="…" size="N">\n{content}\n</file>`; before insertion, escape user-controlled delimiters (`</file>`, triple backticks, `<|`) so file content can never break out into instructions. Never let raw file content reach a system prompt unfenced.

**Audit per op (JSON line):** `ts, op, requested_path, resolved_path, symlink_targets, size_bytes, entry_count, binary_flag, risk_tier, decision`. Log BOTH the original requested string and the resolved path; log every **rejected escape attempt** with the original input. Never log file contents (log only size + a short hash of the first 64 B).

## 4. Steps (test every guard)
1. `local_hands_enabled()` + `hands_root()` (init/create/resolve root).
2. `safe_resolve(rel)` with ALL §3 path checks → returns Path or raises a rejected-escape error (audited).
3. `fs_list(rel)`, `fs_read(rel)`, `fs_stat(rel)` with the limits + binary guard + injection fence.
4. `/fs list|read|stat <rel>` command (explicit only; R0; off unless flag) wired into dispatch + a help line.
5. Audit logging per op + rejected-escape logging.
6. `docs/implementation/L4_69_LOCAL_HANDS_V1.md`.

## 5. Tests (tests/test_ai_council.py) — guards MUST bite
- Escape attempts ALL rejected: `../etc/passwd`, `..\\..\\win.ini`, `C:\\Windows`, `\\\\server\\share`, an absolute path, and a symlink inside the root pointing outside (create one in a temp sandbox) → each raises/var rejected and is audited; the real target is never read.
- Containment: a file inside the root reads correctly; `is_relative_to` holds.
- Limits: a >1 MiB file rejected; a dir with >1024 entries aborts; a file with a `\\0` byte returns `[binary omitted]`.
- Injection fence: a file containing `</file>` and triple backticks comes back escaped/fenced, not breaking the wrapper.
- Off by default: with `AI_COUNCIL_LOCAL_HANDS` unset, `/fs read x` refuses.

## 6. Safety boundaries (worker MUST NOT)
- No write/delete/move/exec, no network, no `.env`/secrets, no deploy/push/daemon. v1 is read-only.
- `local_fs` stays OUT of `LLM_ROUTER_ALLOWED_COMMANDS` (explicit commands only).
- Off by default; every op R0 + audited; no path guard removed or softened.

## 7. What Claude reviews on return (adversarial)
Path-containment correctness is the whole ballgame: try to break `safe_resolve` with parent-symlink escape, Windows 8.3 short names, trailing-dot/space tricks, case-insensitivity, and TOCTOU (resolve vs open). Verify limits + binary + injection fence bite, off-by-default holds, audit captures rejected escapes. Only then is host trial (still read-only) considered.

## 8. Follow-up layers (NOT here)
L4.69.1 write ops (create/append) behind R3 approval + dry-run + verify + rollback (inverse-op log); L4.70.5 multi-step execution with checkpoint/rollback. v1 must prove the read-only sandbox is airtight first.
