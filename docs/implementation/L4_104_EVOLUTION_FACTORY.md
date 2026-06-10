# L4.104 — Evolution Factory (pętla rozwoju, 5 stacji)

Data: 2026-06-10. Mac worktree, NIE wdrożone. System przestaje czekać na błędy:
raz dziennie sam szuka jednej wartościowej zmiany dla Bartka i przepuszcza ją
przez ISTNIEJĄCY, gated pipeline self-repair. Zero nowych daemonów, zero nowych
uprawnień — wszystko przez istniejący `serve`/recipes i guardy L4.101–L4.103.

## Stacje

1. **ZWIAD — `evolution_research_pack()`**: jedno wywołanie Groka (reserve/finalize
   wewnątrz `grok_response`), prompt: nowości/wzorce osobistych agentów AI (X, Reddit,
   GitHub trending; Poke-like UX, pamięć, narzędzia, integracje) → 5–8 pomysłów
   z 1-zdaniowym uzasadnieniem. Raport: `REPORTS_DIR/evolution-research-YYYYMMDD.md`
   (istniejący raport dnia jest reużywany — bez drugiego strzału do Groka).
   Grok zablokowany/padnięty → `""` + `record_error("evolution_research")`, cykl idzie dalej.
2. **LUSTRO+PLAN — `evolution_analyze_and_plan()`**: wsad = raport zwiadu + top błędy
   actionable 24h (`evolution_top_errors`) + tury Bartka dziś/wczoraj
   (`evolution_user_turn_counts`, tail-first z `CONVERSATIONS_FILE`) + 3 ostatnie
   improvements. Jedno wywołanie Claude CLI bez tools (`evolution_claude_plan`,
   wzór `poke_chat_claude_response`: `--tools ""`, `--append-system-prompt
   EVOLUTION_PLAN_CONTRACT`, `reserve_operator_call("claude", detail="evolution")`).
   Wynik: WYŁĄCZNIE JSON `{"title", "why_for_bartek", "kind": "self_repair"|"manual",
   "task"}`; `parse_evolution_plan` parsuje defensywnie (zepsuty JSON → None +
   `record_error("evolution_plan_parse")`).
3. **BUDOWA**: `kind=self_repair` → `run_self_repair_once(goal={context: "goal:<slug>",
   task, title})`. Goal jedzie TĄ SAMĄ ścieżką co naprawa błędu: izolowana kopia,
   pełny pytest, R2 action, `self_repair_guard_auto_apply` + adversarial review przy
   AUTO_APPLY, backup + undo. Jedyna różnica to prompt (`self_repair_goal_section`:
   „ZADANIE DO WDROZENIA… NO_SAFE_PATCH gdy za duże"). `kind=manual` →
   `create_improvement(source="evolution_factory", priority="P2")`.
4. **KONTROLA**: w pipeline self-repair (bez zmian w guardach — ani jednej linii).
5. **GŁOS**: na końcu, NIEZALEŻNIE od wyniku, JEDNA krótka wiadomość po polsku przez
   `deliver_proactive` (iMessage primary). Marker dzienny `state/evolution_factory.json`
   (wzór morning_brief, zapis NAJPIERW) — maks 1 cykl i 1 wiadomość dziennie.

## Puls użycia

Jeśli tur Bartka dziś == 0, zamiast raportu idzie zachęta z JEDNĄ konkretną
propozycją użycia opartą o `active_user_facts` (`evolution_usage_pulse_message`).

## Rejestracja

- Recipe `evolution_factory_daily` w `default_recipes()` (managed jak
  `error_audit_twice_daily` przez `DEFAULT_RECIPE_MANAGED_KEYS`), cron
  `0 <AI_COUNCIL_EVOLUTION_HOUR_UTC, default 3> * * *`, krok `{"command": "/evolve"}`.
  UWAGA: `recipe_due_window` porównuje czas LOKALNY hosta — nazwa env mówi UTC
  (zgodnie ze specyfikacją), ale na Windows z TZ CEST godzina 3 = 3:00 lokalnie.
- `/evolve` w `route_text` (operators host, mode `evolution`), w `BACKGROUND_COMMANDS`
  (działa w tle) i w `READONLY_RECIPE_COMMANDS` (inaczej recipe policy deny-by-default
  blokowałaby krok — tak jak dziś blokuje `/self-repair` w `self_repair_loop.json`).
- CLI: `python ai_council.py evolution [--send] [--force]` (`--force` ignoruje marker
  dzienny — do testów ręcznych).
- Flagi: `AI_COUNCIL_EVOLUTION_ENABLED` (default true), `AI_COUNCIL_EVOLUTION_HOUR_UTC`
  (default 3), `AI_COUNCIL_EVOLUTION_MODEL` (fallback `AI_COUNCIL_POKE_CHAT_CLAUDE_MODEL`),
  `AI_COUNCIL_EVOLUTION_TIMEOUT` (default 180 s).

## Bezpieczniki

Produkcję zmienia wyłącznie pipeline self-repair (R2 `/approve` albo AUTO_APPLY za
guardem AST + adversarial review). Fabryka sama: czyta, planuje, zapisuje raport/
improvement i wysyła jedną wiadomość. Budżety operatorów respektowane przez
reserve/finalize. Marker-first = zero spamu przy retry/crashu.

## Weryfikacja (Mac, 2026-06-10)

- `python3 -m pytest -q tests` → **601 passed, 180 subtests** (21 nowych w
  `tests/test_evolution_factory.py`: parsowanie planu dobry/zepsuty, marker 1/dzień,
  puls użycia 0 tur, liczenie tur tylko role=user, recipe zarejestrowana + policy
  clean + godzina z env, routing `/evolve` + background + dispatch `send=True`,
  research fail-safe (blocked/wyjątek/reuse raportu), goal→pipeline z `/approve`,
  manual→improvements, goal-prompt + guard pustego goal).
- `py_compile` OK, `ruff check` clean. Testy hermetyczne: żywy Grok/Claude nigdy nie
  jest wołany (patch `grok_response`/`evolution_claude_plan`/`run_self_repair_once`).

## Znane kompromisy v1

- `recipes/self_repair_loop.json` (L4.101) ma krok `/self-repair`, którego NIE ma w
  `READONLY_RECIPE_COMMANDS` — scheduler blokuje go policy (`recipe_step_policy`
  warning co wieczór). Nie ruszane w tym sprincie; `/evolve` świadomie dodany do
  allowlisty, żeby nie powielić problemu. Do osobnej decyzji: dodać `/self-repair`
  do `READONLY_RECIPE_COMMANDS` albo wyłączyć recipe.
- Kolizja wersji: w worktree istnieje niezacommitowany `L4_104_DEEPAGENTS_ADAPTER.md`
  (`DEEPAGENTS_ADAPTER_VERSION = "L4.104"`). Przy commicie zdecydować, który layer
  dostaje numer L4.104, a który L4.105.
- Godzina 3 w nocy wpada w quiet hours (`AI_COUNCIL_QUIET_*`), ale `deliver_proactive`
  ich nie sprawdza — wiadomość trafi do iMessage outbox nocą; Mac runner i tak
  dostarczy ją, gdy działa. Jeśli to budzi, przestawić `AI_COUNCIL_EVOLUTION_HOUR_UTC`.
