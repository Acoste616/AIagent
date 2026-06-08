# L4.67 (partial) — Error Signal Hygiene

Date: 2026-06-08 · Owner: Claude Opus 4.8
Status: severity-aware actionable count LANDED + tested. Dedup/suppression of recurring signatures = follow-up.

## Why
`errors_24h ≈ 50` on the live host, but the prior audit found most are benign/noisy (severity `warning`/`info`). A single blended count makes the health signal useless — you can't tell real failures from noise.

## Change
- `actionable_error_rows(rows)` (+ `BENIGN_ERROR_SEVERITIES = {"warning","info"}`): filters to errors that likely need action; a row missing `severity` is treated as actionable (conservative).
- `front_runtime_snapshot()` adds `errors_24h_actionable`.
- `/front` reliability health line 6 now shows `errors_24h: N (actionable: M)`.

## Tests
`ErrorHygieneTests::test_actionable_error_rows_excludes_benign_noise` — warning/info excluded, missing-severity + ERROR (case-insensitive) counted. Suite: **325 passed**.

## Follow-up (L4.67 full)
Per-signature dedup of recurring errors, benign-source suppression list, and wiring `errors_24h_actionable` into the autonomous error-audit loop so it clusters real root causes instead of counting noise.

## Safety
Read-only/reporting change; no behavior change to error recording or any gate.
