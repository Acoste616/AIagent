# L4.72 — Proactive Morning Brief + Nudge Engine + DND

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: LANDED + DEPLOYED + ENABLED (367 passed Mac+Windows).

Zamyka lukę #3 z audytu Poke-parity ("własny głos o 8:00") — **autonomicznie, bez żadnej zewnętrznej autoryzacji** (brief z danych wewnętrznych).

## Co robi
- **Poranny brief** (`build_morning_brief`): raz dziennie składa digest z WEWNĘTRZNEGO stanu — akcje czekające na decyzję, fakty do potwierdzenia (`/memory pending`), otwarte improvementy, taski stuck, błędy wymagające akcji — plus "Pamiętam: …" (top aktywne fakty). **'wait'-logika**: jeśli nic ważnego, zwraca "" i NIE wysyła (zero spamu).
- **Scheduler**: `maybe_send_morning_brief` wpięte w pętlę `serve()` obok `run_due_recipes`/`run_proactive_scan`. Fire raz/dzień po `AI_COUNCIL_BRIEF_HOUR_UTC` (domyślnie 6 UTC ≈ 8:00 CEST); marker `state/morning_brief.json` (`last_brief_day`) zapisywany PRZED wysyłką → brak retry/spamu nawet przy pustym briefie albo błędzie wysyłki.
- **Cisza nocna (DND)**: `in_quiet_hours` (domyślnie 21–05 UTC ≈ 23–07 CEST) — `run_proactive_scan` dalej WYKRYWA eventy, ale nie pinguje w nocy (adresuje ryzyko "3am ping" z krytyki).
- **`/brief`** — wymusza pokazanie briefu na żądanie (ignoruje dedup/godzinę). Off-day → "Nic pilnego — brief pusty (cisza)."
- Respektuje `/control` (proactive_paused), `AI_COUNCIL_PROACTIVE_BRIEF` (gate, **enabled na hoście**), `TELEGRAM_ALLOWED_CHAT_ID`.

## Anchors
`serve()` loop (~15877), `run_proactive_scan` (~10010, +DND), nowe: `in_quiet_hours`/`build_morning_brief`/`morning_brief_due`/`maybe_send_morning_brief` + marker helpers (przed `maybe_send_action_nudges`). Komenda `/brief`: registry + route_text + build_response.

## Tests (MorningBriefTests, 6)
quiet-hours night/day, brief empty-when-nothing ('wait'), brief content-when-pending, off-by-default, sends-once-then-marks (dedup), command-routes.

## Verification
- Mac + Windows: **367 passed**; ledger md5 unchanged.
- Live na produkcji: `/brief` → `☀️ Poranny brief — … Pamiętam: mój lot jest w piątek • ⏳ 30 akcji…` (realny stan).
- Flaga `AI_COUNCIL_PROACTIVE_BRIEF=true` ustawiona na hoście (surgical .env edit, secrets verified). Brief poleci codziennie ~8:00.

## Naprawione przy okazji (testy env-zależne odsłonięte przez włączone flagi hosta)
`test_source_search_github_requires_auth_*` / `_public_fallback_*` (zakładały brak GITHUB_TOKEN — teraz patchują cfg) + `test_auto_extract_off_when_flag_disabled` (zakładał FACT_AUTO_EXTRACT off). Teraz env-niezależne.

## Follow-up
Gdy podłączysz Gmail/Calendar (auth) — brief wzbogaci się o realny kalendarz dnia + ważne maile (Poke-style). Realtime watchery email/event = osobna warstwa.
