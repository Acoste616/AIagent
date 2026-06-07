# L4.60 Poke Research Pre-pass

## Purpose

Bartek's goal requires Grok to actively collect Poke/OpenClaw/Hermes research before Claude and Codex plan implementation. Live behavior still depended too much on explicit slash commands or the literal word `research`.

L4.60 makes natural Poke parity/build messages start the safe Grok X+web pre-pass automatically.

## Changes

- Added `POKE_RESEARCH_PREPASS_VERSION = "L4.60"`.
- Added natural intent detection for Poke/@interaction parity, clone, missing-feature, integration, and implementation research language, including Poke-targeted OpenClaw, Hermes, iPhone, Apple Messages, and developer-context mentions.
- Routes matching Poke build/research intent to `/poke-research` in background with a Grok pre-pass prompt.
- Keeps pure frustration such as `nie odpowiada jak poke...` on the short `/poke-gap` path unless the message asks to investigate, compare, clone, or plan.
- `/agent next` can now expose `RUN: /agent run feature_evolution_loop` when the inbox is empty, so the safe R0 Grok->Claude evolution loop is runnable from the compact operator card.
- `/health` exposes `poke_prepass=L4.60`.

## Safety

- No shell execute.
- No external write.
- No daemon changes.
- The pre-pass uses the existing `/poke-research` background task, idempotency, progress, cost guard, artifacts, and Telegram delivery flow.

## Verification

- Natural Poke/OpenClaw/Hermes clone intent routes to Grok `/poke-research`.
- `sprawdź czego brakuje do Poke...` routes to Grok `/poke-research`.
- Pure Poke frustration still returns `/poke-gap`.
- Benign Poke mentions such as checking whether a local recipe works do not start the paid Grok pre-pass.
- Empty `/agent next` exposes a runnable `feature_evolution_loop`.
