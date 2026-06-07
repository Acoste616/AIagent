# L4.20 Progress UX

Date: 2026-06-07

## Goal

Make long Telegram tasks feel alive and operator-like instead of silent.

This is not token-level streaming. It is a practical Telegram progress layer for background work.

## Implemented

- Background job start response now uses a structured stage card:
  - `ETAP: START`
  - route summary
  - `/status`
  - `/cancel`
  - `/details`
- Background worker now sends a second stage card:
  - `ETAP: RUNNING`
  - route summary
  - status/cancel/details buttons
- Final background result still uses the existing delivery card with:
  - Status
  - Details
  - Facts
  - Next
- Cancelled and failed jobs now use structured progress messages.
- `/goal`, `/status`, and `/selftest` report L4.20.

## Why It Matters

The main Poke-like failure mode was not only missing integrations. It was that long work could feel like silence. L4.20 makes the Telegram flow show immediate start, active running state, and final delivery.

## Remaining Gap

Poke parity still needs:

- unified front orchestrator with one host voice;
- token-level streaming or richer step-by-step progress for long model calls;
- deeper source-backed integrations;
- iPhone Shortcuts as primary capture;
- private iMessage bridge after Telegram core is stable.

## Verification

Local:

```text
python3 -m py_compile ai_council.py tests/test_ai_council.py
python3 -m unittest tests/test_ai_council.py
```

Expected:

```text
Ran 147 tests
OK
```
