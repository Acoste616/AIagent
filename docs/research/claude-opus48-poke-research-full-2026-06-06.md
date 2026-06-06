<!-- started=2026-06-06T23:02:05 ended=2026-06-06T23:08:59 exit=0 model=claude-opus-4-8 -->

Pełny raport poniżej — w całości w odpowiedzi (stdout), zgodnie z wymaganiem. Wszystko zweryfikowane samodzielnie w kodzie i źródłach; fakty oddzielone od hipotez, unknowns oznaczone.

---

# Claude Opus 4.8 Full Research + Solution Design

> Tryb: research + solution design (read-only). Nie wykonano żadnego write/send/publish poza plikiem raportu. Nie użyto sekretów.
> Oznaczenia: **[FAKT]** = zweryfikowane w kodzie/źródłach w tym przebiegu. **[HIPOTEZA]** = wniosek/projekt. **[UNKNOWN]** = niezweryfikowane, do decyzji/sprawdzenia.

## 1. Research Summary

- **[FAKT]** `ai_council.py` to monolit ~3501 linii / 137 KB, **czysto stdlib** (argparse, sqlite3, subprocess, urllib, threading, difflib, hashlib — zero zależności zewnętrznych). Realny messaging-core na Telegramie: routing PL, background jobs z prawdziwym kill PID, approval gate, pamięć SQLite+FTS5, cost ledger.
- **[FAKT]** `tests/test_ai_council.py` ma **38 metod testowych** (zweryfikowane `grep "def test_"`). **Korekta wobec poprzedniego summary, które twierdziło „27/27 przechodzi to fakt"** — liczba jest inna, a statusu pass/fail **nie weryfikowałem w tym przebiegu** (read-only, nie uruchamiałem testów). → [UNKNOWN: aktualny wynik].
- **[FAKT]** Poke wygrywa **UX-em, nie technologią**: recipes („10 s"), in-thread action buttons, zero-friction, ton/voice, brak limitów czatu.
- **[FAKT]** Najczęstsza realna skarga userów Poke: **brak transparentności kosztów + brak metryk i lokalnego dashboardu**. Tu AI Council ma gotową przewagę (cost ledger).
- **[FAKT]** Lekcja OpenClaw (`WORKING_MEMORY.md`): „wrote it ≠ delivered it" w 4 warstwach, 0 PLN po ~38 dniach — brak warstwy **dostarczania**. Wniosek: każda funkcja musi parować „write" z „deliver".
- **[FAKT]** Brakuje dokładnie tego, co u Poke jest core'em: **recipes i przyciski inline**. Potwierdzone w kodzie: brak `inline_keyboard`, `callback_query`, `reply_markup`, `answerCallbackQuery`, `recipe`, `voice`.

## 2. Poke Feature Inventory

| Funkcja | Status | Szczegół |
|---|---|---|
| Apple Messages / iMessage | **[FAKT]** | Pierwszy AI agent zatwierdzony przez Apple (Messages for Business), 2026-06-04 (post 2062575428213285352). |
| Recipes | **[FAKT]** | Core. „Przepis" w ~10 s tekstem, bez kodu. Shareable, „Earn on Poke". Gmail/Calendar/Notion/Strava/Swiggy. |
| Zero-friction onboarding | **[FAKT]** | „No download, no signup. Text Poke for free." Jeden tap. |
| Kanały | **[FAKT]** | SMS, Telegram, WhatsApp + iMessage Business. >100 mln wiadomości. |
| In-thread action buttons | **[FAKT]** | Przyciski + dynamiczne linki (Stripe) w wątku. Chwalone po update. |
| Ton/voice | **[FAKT]** | „Gets voice and tone right." |
| Brak limitów czatu | **[FAKT]** | Image gen limitowane (koszt), chat bez limitów. |
| `npx poke` (dev) | **[FAKT]** | CLI do własnych agentów/integracji. |
| Szybkość/reliability | **[FAKT]** (claim) | „biggest infrastructure update ever" — bez liczb. |
| Pricing | **[FAKT]** (z postów) | Pro ~15 USD/mc, negocjowalne do ~0,99 USD. |
| Proactive nudges + memory | **[HIPOTEZA/UNKNOWN]** | „Prawie zero wzmianek" — prawdopodobnie słabo rozwinięte. |
| Voice notes → akcja | **[FAKT]** | Wspomniane jako wejście. |

## 3. Poke Unknowns / Non-Hallucination Boundaries

- **[UNKNOWN]** Architektura backendu, model LLM, latency w liczbach — brak danych publicznych.
- **[UNKNOWN]** Czy Poke używa MCP — w postach Poke brak; MCP tylko w ogólnych dyskusjach AI, niepowiązanych.
- **[UNKNOWN]** Apple Messages internals — wiemy tylko: oznaczenie „AI" + human handoff + custom UI zgodny z Apple. Implementacji nie halucynuję.
- **[UNKNOWN]** Mechanika „Earn on Poke"/marketplace recipes (rozliczenia).
- **[UNKNOWN]** Jak działa memory/proactivity (persistent per-user? trigger nudge'ów?).
- **[UNKNOWN]** Czy „human-in-the-loop" jest trwały, czy tylko Apple-channel.

Te punkty wchodzą do projektu jako „zaprojektuj własny odpowiednik", nie „skopiuj X".

## 4. Current AI Council Inventory

Klasyfikacja ✅ działa / 🟡 szkielet / ❌ brak — wszystko **[FAKT]** z lektury, numery linii z `ai_council.py`.

**Routing & wejście**
- ✅ Routing naturalny PL (`natural_intent_route`, L2434) — ~40 fraz (status, health, koszty, cancel/anuluj, details/szczegóły, fakty, next, kolejka, task, actions, approve/deny, zapamiętaj, wyszukaj w pamięci, write/append/patch, council, flow, xresearch, poke).
- ✅ Routing explicit (`route_text`, L2683): `@codex @claude @claude-flow @grok @research @xresearch @all` + ~30 komend `/…`.
- ✅ Multiline → `/multi` (`multiline_command_route`, L2654; max 5 linii), wykonywany w `build_response` (L3083).

**Operatorzy** (`build_response`, L3079)
- ✅ Codex read-only (`codex_response`, L2819) — `codex exec --skip-git-repo-check --sandbox read-only`.
- ✅ Claude quick bez tools (L2837).
- ✅ Claude Flow Opus 4.8 (L2873) — `--model claude-opus-4-8 --permission-mode plan`, bez budżet-cap, timeout 600 s.
- ✅ Grok (L2907/3053) + Grok X research przez xAI x_search (L2996; parser L2951).

**Background jobs / niezawodność**
- ✅ `start_background_job` (L448) — `Popen` + spec + `worker_pid`; `route_should_background` (L396).
- ✅ Real cancel PID (`terminate_pid` L512, `cancel_response` L1760) — idempotentny, nie zabija ukończonych.
- ✅ `reconcile_background_jobs` (L575) — sieroty po restarcie → failed.
- ✅ Idempotency (L602/607), stuck detection (L630), Telegram chunking 4000 (L2345/2362).

**Pamięć** — ✅ SQLite + FTS5 (L1058/1088/1169) + auto-recall do promptu (L1205).

**Koszty** — ✅ Cost ledger (L916/947/967), Grok daily call+budget guard. `/cost` to **tekst** (L986); Codex/Claude przez subskrypcję = brak per-call billing (jawnie zaznaczone).

**Approval gate / workspace** — ✅ Actions pending→approve/deny (L1251/1642/1675), workspace write/append/patch + diff preview (L1311), path-escape rejected (L1287).

**Artefakty** — ✅ `save_task_artifacts` (L788) + index, details/facts/next (L855/876/890), structured council v0 (L1864: Claude propose / Grok red-team / Codex feasibility).

**Health/bezpieczeństwo** — ✅ `/health` bez network (L1032), `doctor` (L3435), `is_allowed_message` allowlist (L3275), redact/sanitize/audit (L147/3180/3190).

## 5. Current UX Failure Analysis

1. **Brak przycisków inline** — [FAKT] `telegram_send_message` bez `reply_markup`; `telegram_updates` nie czyta `callback_query`. → [HIPOTEZA] approve/deny/cancel wymaga ręcznego `/approve <id>`, wysokie tarcie, literówki w ID.
2. **Brak recipes** — [FAKT] `/multi` jest ad-hoc, nie zapisuje/nazywa/parametryzuje. → [HIPOTEZA] powtarzalne workflowy od zera; to dokładnie UX, który Poke sprzedaje jako „10 s".
3. **Koszty jako surowy tekst** — [FAKT] `/cost` zwraca linie. → [HIPOTEZA] przewaga niedostarczona, bo nieczytelna.
4. **Brak proaktywnego delivery-nudge** — [FAKT] worker wysyła jeden finalny komunikat (L1988). → [HIPOTEZA] powtórka błędu OpenClaw „wrote ≠ delivered".
5. **Brak voice** — [FAKT] brak transkrypcji. → [HIPOTEZA] tarcie mobilne.
6. **ID-driven UX** — [FAKT] nawigacja po `task_id`/`action_id` ręcznie. → [HIPOTEZA] mentalnie kosztowne; Poke ukrywa ID za przyciskami.
7. **Capabilities jako ściana tekstu** — [FAKT] `capabilities_response` (L1005). → [HIPOTEZA] słaba odkrywalność.

## 6. OpenClaw Assets To Reuse

**Reuse (wzorce):**
- **[FAKT]** Autonomy boundaries AUTO/SHOW-AND-GO/ASK (`OPERATING_CONTEXT.md`) — mapuje 1:1 na approval gate. Kanon dla recipes/safe-exec.
- **[FAKT]** Daily Loop (orient→execute małymi krokami→verify→distill) — wzorzec recipe-runner/nudge.
- **[FAKT]** Intent discipline (lock domeny z PL skrótów, stop przy korekcie).
- **[FAKT]** **Building ≠ Delivering** — paruj „write" z „deliver"; uzasadnia nudge engine.
- **[FAKT]** Memory-first gate — już częściowo w auto-recall.

**NIE kopiować ([FAKT] retired):** VPS Hetzner `46.225.115.173` (OFF od 2026-04-20, skill ARCHIVED); Trio OpenClaw+Hermes+Claude (retired, single-runtime); Maya/EVDrive/Tesla/Valentyna jako aktywne (CLOSED 2026-05-07); Company OS/MI/ledger (inny system).

## 7. Hermes Assets To Reuse

Reuse = **wzorce kodu, NIE runtime** (Hermes nie wspiera Windows natywnie — wymaga WSL2; nasz core jest Windows-stdlib).

- **[FAKT]** **Command registry** (`hermes_cli/commands.py`, `COMMAND_REGISTRY`/`CommandDef`) — jedno źródło → CLI/gateway/Telegram menu/help/autocomplete pochodne. Wzorzec na refaktor `route_text`/`build_response` + auto-generacja Telegram menu i przycisków.
- **[FAKT]** **Tool registry + auto-discovery** (`tools/registry.py`, handler→JSON) — wzorzec na recipe-steps.
- **[FAKT]** **MemoryProvider ABC** (`agent/memory_provider.py`) — kształt interfejsu na przyszłość; SQLite na razie wystarcza.
- **[FAKT]** **Cron scheduler** (`cron/scheduler.py`) z dostawą na platformę — wzorzec scheduled nudges.
- **[FAKT]** **Background notifications** (`notify_on_complete`, verbosity all/result/error/off) — polityka głośności nudge'ów.
- **[FAKT]** **Dwie warstwy guardów bramki** — komendy kontrolne (/stop,/approve,/deny) muszą omijać kolejkowanie gdy agent zajęty. Krytyczne dla callbacków przy trwającym jobie.
- **[FAKT]** **Cache-aware mutacje** (deferred + `--now`) — wzorzec zmian recipe.
- **[FAKT]** Polityka „no change-detector tests" + invarianty — przyjąć w testach.

**NIE kopiować:** TUI Ink/React, profile/HERMES_HOME, ACP, RL/Atropos, pełny plugin system, multi-platform gateway. Za ciężkie dla jednoosobowego core.

## 8. Target Feature Design (≥10 funkcji, P0–P3)

- **F1 — Recipe Engine (P0).** Zapisane/nazwane/parametryzowane multi-step. Storage `state/recipes.jsonl` (wzorzec append_jsonl/latest_by_id L267/291). Silnik: reuse `/multi` (L3083), placeholdery `{1}`/`{nazwa}`. Komendy `/recipe-new`,`/recipe-run`,`/recipes`,`/recipe-del` + PL „przepis". Deterministyczne, bez „LLM-magii".
- **F2 — Inline Action Buttons (P0).** `reply_markup` w `telegram_send_message` (L2362) + `callback_query` w `telegram_updates`/`listen_once` (L2315/3284) + `answerCallbackQuery`. Callback data `approve:/deny:/cancel:/recipe:`. Mapuje na istniejące `*_response`.
- **F3 — Delivery Nudge Engine (P1).** Po jobie/przy pending action: „✅ gotowe — [Zatwierdź][Szczegóły]". Reuse `run_background_job` (L1988) + `actions_response` (L1627). Realizuje OpenClaw „deliver".
- **F4 — Cost Dashboard (P1).** `/cost` (L986): dziś vs limit (% budżetu Grok), per-operator, top-N, próg-ostrzeżenie. Reuse `operator_usage_summary`/`operator_call_allowed`. Przewaga nad Poke.
- **F5 — Capabilities jako menu przycisków (P2).** `/capabilities` (L1005) → inline keyboard + lista recipes.
- **F6 — Scheduled Nudges / mini-cron (P2).** NL→`state/schedules.jsonl`, sprawdzanie w `serve` (L3416). Wzorzec Hermes cron. PL „przypomnij".
- **F7 — Voice → tekst (P3).** Telegram voice→STT→router. [UNKNOWN: dostawca STT] → [DECYZJA], łamie pure-stdlib. Domyślnie odłożone.
- **F8 — Recipe export (P3).** Eksport do `workspaces/shared` przez approval gate. Prywatny odpowiednik „Earn on Poke" bez marketplace.
- **F9 — Command/Recipe registry refactor (P1).** Jeden rejestr (wzorzec Hermes) → auto-generacja Telegram menu/przycisków/help. Redukuje dług.
- **F10 — iPhone Shortcuts bridge (P2).** Wariant Telegram (skrót→wiadomość, zero infra) — ~95% wartości „Apple-like" bez Apple Business. Alt: HTTP przez Tailscale [UNKNOWN].
- **F11 — Safe-execution L3 (P3, opcjonalne).** Shell-exec za approval + denylist (wzorzec Hermes). Najwyższe ryzyko → [DECYZJA].
- **F12 — Memory-backed recall przy recipe (P2).** Auto-wstrzyknięcie pamięci (jest `memory_context_for_prompt`) + zapis wyniku recipe do pamięci.

## 9. Deployment Plan With Dependencies

- **Etap 0 — Patche pod tournament (P0).** Sekcja 10. Bramka: nowe testy + 38 istniejących zielone.
- **Etap 1 — Buttons + Recipes (P0).** F2 → F1 (F1 używa F2 do `/recipe-run` przyciskiem). Bramka: approve przyciskiem E2E; recipe round-trip.
- **Etap 2 — Delivery + Cost (P1).** F3 (zależy od F2) + F4 (niezależne). Bramka: nudge po jobie; `/cost` z % budżetu.
- **Etap 3 — Registry refactor + Capabilities menu (P1/P2).** F9 → F5. Zależność: F1/F2 stabilne. Bramka: auto-generowane Telegram menu.
- **Etap 4 — Scheduled nudges (P2).** F6. Zależność: F3 (kanał dostawy). Bramka: zaplanowany recipe-run, idempotentny.
- **Etap 5 — iPhone Shortcuts (P2).** F10 wariant Telegram. Zależność: F1. Bramka: skrót iOS uruchamia recipe.
- **Etap 6 — Opcjonalne (P3).** F7/F8/F11 — każde po decyzji Bartka.

Odłożone świadomie: Apple Messages (bariera 2–3 mies.), safe-exec L3 (ryzyko).

## 10. Minimal Immediate Patches For Codex (≥8)

1. **PATCH-1:** `reply_markup: dict|None=None` w `telegram_send_message` (L2362), dołożony do payloadu jako JSON. Backward-compatible.
2. **PATCH-2:** obsługa `callback_query` w `telegram_updates` (L2315) i `listen_once` (L3284): czytać `data`, mapować `approve:/deny:/cancel:/recipe:`, wołać `answerCallbackQuery`, respektować allowlist na `from`/`chat` callbacku.
3. **PATCH-3:** helper `build_action_keyboard(action_id)` → `[[Zatwierdź|approve:id, Odrzuć|deny:id]]`; użyć w `/propose`/`actions_response`/approve flow.
4. **PATCH-4:** recipe storage `state/recipes.jsonl` + `recipe_save/recipe_get/recipes_list/recipe_delete` (wzorzec `memory_save`/`latest_by_id`).
5. **PATCH-5:** routing recipe w `route_text` (L2683) + `natural_intent_route` (L2434): `/recipe-new`,`/recipe-run`,`/recipes`,`/recipe-del` + PL „przepis"/„uruchom przepis"; gałęzie w `build_response` (reuse `/multi`).
6. **PATCH-6:** `/cost` dashboard (L986) — linia budżetu Grok (spent/limit, %), próg ≥80%. Reuse `operator_call_allowed` + env.
7. **PATCH-7:** nudge po jobie w `run_background_job` (L1988) — inline keyboard (PATCH-3) przy pending action/next-actions.
8. **PATCH-8:** aktualizacja `capabilities_response` (L1005) + `system_status_response` (L1016) — by nie kłamały o możliwościach.
9. **PATCH-9 (testy):** callback→route, recipe round-trip, `reply_markup` w payloadzie, cost-budget %, recipe path/escape. Bez change-detector.
10. **PATCH-10 (anty-halucynacja):** wpis w capabilities/README, że Apple Messages i voice są świadomie poza zakresem.

## 11. Acceptance Criteria (≥12)

1. Wiadomość z `reply_markup` pokazuje przyciski w Telegramie (ręczna weryfikacja).
2. „Zatwierdź" wykonuje `approve_response(<id>)`, status → executed/approved.
3. „Odrzuć" → status denied; brak skutku na plikach.
4. Callback od nieautoryzowanego user/chat ignorowany (test + audit).
5. `/recipe-new nazwa = krok1 ; krok2` zapisuje do `recipes.jsonl` i potwierdza.
6. `/recipe-run nazwa arg` wykonuje kroki przez `/multi`, zwraca per-krok wynik.
7. `/recipes` listuje; `/recipe-del nazwa` usuwa (soft append).
8. Placeholder `{1}` podstawiany argumentem `/recipe-run`.
9. `/cost` pokazuje dla Grok: liczbę calli, % budżetu, flagę ≥80%.
10. Po jobie z pending action przychodzi nudge z przyciskami (nie sam tekst).
11. `/capabilities` i `system_status_response` wymieniają nowe komendy — brak rozjazdu deklaracja↔kod.
12. **38 istniejących testów nadal przechodzi** + nowe z PATCH-9 zielone.
13. Żadna nowa funkcja nie robi shell/zapisu poza `WORKSPACES_DIR`/external bez approval (regresja = fail).
14. Brak nowych zależności (core pure-stdlib) — `import` check.
15. Recipe z path-escape lub side-effect bez approval odrzucony.

## 12. Test Plan

**Jednostkowe (nowe, wzorzec `unittest`+`temp_dir()`+`patch.object`):** `test_telegram_send_message_includes_reply_markup`; `test_callback_query_maps_to_approve/deny/cancel/recipe`; `test_callback_from_unauthorized_user_ignored`; `test_recipe_save_run_list_delete_roundtrip`; `test_recipe_run_substitutes_placeholder_args`; `test_recipe_rejects_side_effect_without_approval`/`_path_escape`; `test_cost_dashboard_reports_grok_budget_percentage`; `test_background_job_final_message_attaches_action_keyboard`; `test_capabilities_mentions_recipe_and_button_commands` (invariant).

**Regresja:** `python -m unittest tests/test_ai_council.py` (38+nowe zielone); `python ai_council.py doctor`.

**E2E ręczne (Telegram po deployu):** (1) `/propose test`→przyciski→Zatwierdź→executed; (2) `/recipe-new rano = status ; koszty`→`/recipe-run rano`→dwa wyniki; (3) `@claude-flow …`→nudge z przyciskiem; (4) `/cost`→% budżetu.

**[UNKNOWN]** Nie uruchomiłem testów w tym przebiegu (read-only). Pierwszy krok implementacji: baseline 38 przez `python -m unittest`.

## 13. Questions / Decisions For Bartek

1. **Apple Messages — robić w ogóle?** Rekomendacja: **odłożyć** (Apple Business approval 2–3 mies., AI-label + human handoff). Telegram + iPhone Shortcuts = ~95% wartości. [DECYZJA]
2. **iPhone Shortcuts — wariant?** (a) skrót→wiadomość do bota (zero infra, działa dziś) — rekomendacja; (b) HTTP bridge przez Tailscale. [UNKNOWN: Tailscale na iPhone?]
3. **Safe-execution L3 — potrzebne?** Read-only Codex + workspace write już są — wystarczą, czy chcesz shell-exec za approval + denylist? [DECYZJA, wysokie ryzyko]
4. **Voice → tekst — który STT?** Łamie pure-stdlib (koszt/zależność). [DECYZJA: pominąć / wskazać dostawcę]
5. **Recipe engine deterministyczny (reuse `/multi`) — zgoda?** Rekomendacja: tak na start. [POTWIERDZENIE]
6. **Czy `gh` jest zalogowane na Desktopie** (gdyby recipes dotykały GitHub)? [UNKNOWN]
7. **Registry refactor (F9) teraz czy po tournament?** Większa zmiana, porządkuje dług. [DECYZJA]

---

### Załącznik: rozbieżności wobec poprzedniego summary
- Poprzedni run: „27/27 testów przechodzi, to fakt". **Korekta:** plik ma **38 metod testowych** (zweryfikowane), statusu pass/fail **nie weryfikowałem** w tym read-only przebiegu — nie powtarzam niesprawdzonego twierdzenia jako faktu.
- Poprzedni run sugerował „pełny dokument w pliku" bez zwrócenia treści. **Korekta:** pełny raport jest powyżej w całości w stdout (i zapisany w `C:\Users\Komputer\.claude\plans\jeste-claude-opus-4-8-abstract-corbato.md`).

---

Raport jest kompletny: 13 sekcji, **12 funkcji docelowych** (wymóg ≥10), **10 patchy** (≥8), **15 acceptance criteria** (≥12), fakty oddzielone od hipotez, unknowns oznaczone, po polsku. Tournament może na nim startować.

Jeśli chcesz, w kolejnym kroku mogę wejść w tryb wykonania i przygotować konkretne diffy dla PATCH-1…PATCH-10 dla Codexa — ale to wymaga wyjścia z trybu plan i Twojej zgody.
