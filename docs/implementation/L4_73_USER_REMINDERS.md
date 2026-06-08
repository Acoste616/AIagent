# L4.73 — User Reminders / Triggers

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: LANDED + DEPLOYED (373 passed Mac+Windows).
Poke-parity: dodaje user-definiowalne automatyzacje/triggery (Poke "Triggers"), w pełni autonomicznie (zero auth).

## Co robi
- `/remind daily HH:MM <tekst>` · `/remind weekly <dzień> HH:MM <tekst>` (pon/wt/śr/czw/pt/sob/ndz lub mon/tue…) · `/remind once YYYY-MM-DD HH:MM <tekst>`
- `/reminders` (lista) · `/remind cancel <id>`
- Scheduler `run_due_reminders` wpięty w pętlę `serve()` (obok briefu) — odpala przypomnienie o właściwej porze, wysyła „⏰ Przypomnienie: …" na Telegram, marker `last_fired` zapobiega podwójnemu odpaleniu; `once` po odpaleniu → status `done`.
- Czas: HH:MM interpretowane lokalnie (`AI_COUNCIL_TZ_OFFSET_HOURS`, domyślnie 2 = CEST), porównywane z UTC. User-set reminders fire o swojej porze (BEZ DND — user wybrał czas).
- Respektuje `/control` (proactive_paused). Storage: `state/reminders.jsonl` (latest-by-id; cancel = append status=cancelled).

## Tests (ReminderTests, 6)
parse (daily/weekly/once + invalid), add/list/cancel, daily due+dedup, run_due fires-once, once→done, command routing.

## Verification
- Mac + Windows: **373 passed**; ledger md5 unchanged.
- Live: `/remind daily 09:00 wypij wode` → „Przypomnienie ✅ (rem-…) codziennie o 09:00"; `/reminders` listuje.

## Przy okazji — conftest neutralizuje flagi (koniec env-fragility)
`tests/conftest.py` wymusza feature-flagi OFF + czyści tokeny (GITHUB/GOOGLE) dla całej suity, więc testy „off by default" są deterministyczne niezależnie od `.env` hosta (gdzie część flag jest teraz ON). Naprawia powracającą klasę awarii (scan/auto-extract/brief) raz na zawsze.

## Follow-up
Naturalny język ("przypominaj co wtorek o 9 że X" → /remind weekly wt 09:00 X) — L4.73.1 (parser PL czasu).

## L4.73.1 — naturalny język (LANDED)
`natural_reminder_to_structured` + prefix route ("przypomnij/przypominaj/remind") konwertuje PL na formę strukturalną:
- "przypomnij mi jutro o 15 że kupić mleko" → `once <jutro> 15:00 kupić mleko`
- "przypominaj codziennie o 8 wypij wodę" → `daily 08:00 wypij wodę`
- "co wtorek o 9:30 raport" → `weekly wtorek 09:30 raport`
- "w piątek o 15 …" → `once <najbliższy piątek> 15:00 …`
**Bramka:** /remind przejmuje TYLKO gdy jest parsowalny czas zegarowy ("o 15", "9:30"); frazy bez czasu ("przypomnij o lekach") spadają do istniejącej ścieżki calendar-draft (L4.35) — bez regresji. Tests: natural parsing + route (8 ReminderTests total). Live: „przypomnij mi codziennie o 8…" → ustawione bez slasha.
