# L4.93 — Claude as Default Front Conversation Operator + Debug-Tail Removal

Date: 2026-06-09
Status: implemented on Mac checkout, NOT yet deployed to `D:\ai-council` (needs Bartek approval + sync, Windows is ahead of Mac on some files).

## What changed

### 1. P0: no debug leaks in user-facing replies

- `strip_debug_metadata(text)` — removes any `route={...}` / `audit_log=...` lines from a reply.
- `respond_dry()` (CLI `respond`) no longer prints the `route=` / `audit_log=` tail by default.
  Diagnostic tail is opt-in: `AI_COUNCIL_RESPOND_DEBUG_TAIL=true`.
- `respond-b64` (iMessage inbound relay) output is additionally scrubbed with `strip_debug_metadata` (defense in depth).
- `front_quality_issues` still records `debug_metadata` as a quality warning if anything slips through.

### 2. P0: Claude is the default conversation operator

Front chat (`/chat` → `poke_chat_response`) now dispatches:

1. cheap local host for tiny ACK/status (`poke_chat_should_use_llm` gate, unchanged);
2. **Claude CLI** (`poke_chat_claude_response`) — default voice, subscription-based, `--tools ""`,
   `--append-system-prompt MASTER_HOST_CONTRACT`, history + memory in the prompt;
3. Grok (`poke_chat_grok_response`) — automatic fallback if Claude is missing/fails/blocked;
4. local `poke_chat_fallback` — last resort.

Grok remains the dedicated research/red-team operator (`@grok`, `@research`, `@xresearch`) — unchanged.
Codex/GPT remain workers (`@codex`, `/delegate`) — unchanged.

`MASTER_HOST_CONTRACT` is now channel-agnostic (iMessage + Telegram).

### New config keys (all optional, safe defaults)

| Key | Default | Meaning |
|---|---|---|
| `AI_COUNCIL_POKE_CHAT_OPERATOR` | `claude` | `claude` or `grok` — front voice |
| `AI_COUNCIL_POKE_CHAT_USE_CLAUDE` | `true` | kill-switch for the Claude chat path |
| `AI_COUNCIL_POKE_CHAT_CLAUDE_MODEL` | (CLI default) | optional `--model` override |
| `AI_COUNCIL_POKE_CHAT_CLAUDE_TIMEOUT` | `90` | seconds |
| `AI_COUNCIL_RESPOND_DEBUG_TAIL` | `false` | re-enable route=/audit_log= tail for diagnostics |

Cost control: the Claude path goes through `reserve_operator_call("claude", detail="poke_chat")` /
`finalize_operator_call`, so existing budget/pause/kill controls apply.

## Tests

- New: `PokeChatClaudeOperatorTests` (default operator, Claude CLI call shape, Grok fallback, debug-tail scrubber).
- Updated: `test_respond_dry_prints_response_and_audits` (asserts NO route=/audit_log= in output);
  three Grok-specific tests now pin `AI_COUNCIL_POKE_CHAT_OPERATOR=grok` to stay hermetic.

## Deploy notes (NOT done — needs approval)

1. Windows production may be ahead of Mac — diff `D:\ai-council\ai_council.py` vs Mac before sync.
2. After sync: run `python -m pytest -q tests\test_ai_council.py` on Windows.
3. Live smoke via iMessage: ordinary message, incomplete request (expect follow-up question),
   "chce jedzenie", "zrob research", verify no debug tail.
4. The Mac bridge (`~/.ai_council/imessage_bridge.py`) uses `respond-b64`; verify the deployed copy
   matches `scripts/mac_imessage_bridge_standalone.py` (which is already clean).
