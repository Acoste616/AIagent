# Bartek Agent OS / AI Council

[![CI](https://github.com/Acoste616/AIagent/actions/workflows/ci.yml/badge.svg)](https://github.com/Acoste616/AIagent/actions/workflows/ci.yml)

Private messaging-first AI operating layer for Bartek. Primary channel: iMessage (phone-number thread via the Mac bridge). Fallback channel: Telegram.

Current production host:

- Windows Desktop over Tailscale
- project path: `D:\ai-council`
- OpenClaw memory path: `D:\openclaw-export`
- Telegram bot: AI Council private bot

## What Works Now

- Telegram listener with allowlist
- natural intent routing
- background jobs for long model calls
- task status, details, facts, next actions
- real cancel for subprocess workers
- Codex read-only operator
- Claude quick operator
- Claude Flow via `claude-opus-4-8`
- Grok chat and Grok X deep research through xAI Responses `x_search`
- memory SQLite
- artifact index
- approved workspace write/append/patch actions
- Windows scheduled task deployment

## Target

Build a private Poke-like assistant that combines:

- Poke UX: messaging-first, low setup, fast responses, recipes, proactive nudges
- OpenClaw: durable memory, operating loop, artifacts, audit
- Hermes: agent skills, workflow discipline, tool execution patterns
- Codex/Claude/Grok: executor, planner, researcher/red-team

Primary channel is iMessage (sender-allowlisted, relayed by the Mac bridge over SSH). Telegram stays as the fallback channel and as the transport for proactive nudges when iMessage is unavailable.

## Run Tests

Always run through pytest so `tests/conftest.py` can sandbox the writable state
directories (running the file directly from a production checkout would write to
the live `state/`):

```bash
python3 -m pytest -q tests
```

On Windows production:

```powershell
cd D:\ai-council
python -m pytest -q tests
python -X utf8 ai_council.py doctor
```

## Grok X Research

```powershell
cd D:\ai-council
python -X utf8 scripts\grok_x_research.py
```

The first Poke research run is saved in:

- `docs/research/grok-x-poke-research-2026-06-06.md`

## Security

Never commit:

- `.env`
- Telegram token
- xAI API key
- OAuth/session files
- logs/state/artifacts with private user data

Use `.env.example` as the template.

