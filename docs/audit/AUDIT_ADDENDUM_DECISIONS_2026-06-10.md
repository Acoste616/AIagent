# Aneks do audytu v2 — decyzje Bartka i korekta planu (2026-06-10)

Uzupełnia `docs/audit/REPO_AUDIT_2026-06-10_v2_CLAUDE_FULL.md`. Stan kodu: `0cc60cc` (L4.102). Bez modyfikacji kodu — to dokument planistyczny.

## 1. Decyzje (zapisane na stałe)

| # | Pytanie z audytu | Decyzja Bartka |
|---|---|---|
| 1 | Widoczność repo / PII w CLAUDE.md | Repo prywatne — PII akceptowalne, bez czyszczenia historii |
| 2 | AUTO_APPLY | **Zostaje. Cel: pełna autonomia napraw.** Hardening zamiast usunięcia |
| 3 | Horyzont życia stanu | **Bezterminowy** — system ma działać bez przerwy; retencja obowiązkowa |
| 4 | Bash w self-repair | **Zostaje pełny** — self-repair musi umieć naprawiać także bash/PowerShell; zabezpieczać środowiskiem, nie kastracją narzędzia |
| 5 | Przegląd deprecjacji env vars | **Zrobić** — wyniki w sekcji 4 poniżej |
| 6 | Latencja vs widoczność | Odpowiedź może trwać dłużej, ale **AI musi sygnalizować, że żyje i pracuje** („pisze…", etapy) — nowy wątek W |

## 2. Korekta planu zadań

### 2a. Zadanie 1.3 (przeprojektowane): AUTO_APPLY zostaje — pakiet strażników

Cel: zielona naprawa wchodzi do produkcji sama, ale złośliwy/ryzykowny patch nigdy nie przechodzi bez `/approve`. Warstwy (wszystkie, nie wybór):

1. **Allowlist plików** — `AI_COUNCIL_SELF_REPAIR_FILES` już istnieje (`ai_council.py:18625`); wymusić ją także w trybie tools (diff vs pristine nie może dotykać plików spoza listy) i dodać twardy limit rozmiaru diffu (np. 400 linii) — powyżej: tylko `/approve`.
2. **Deny-list funkcji bezpieczeństwa** — patch, którego diff dotyka którejkolwiek z: `imessage_sender_allowed`, `is_allowed_message`, `safe_resolve`, `approve_response`, `update_action_status`, `redact_secrets`, `shortcut_authorized`, `self_repair_*`, `provider_write_gate_blockers` — **nigdy** auto-apply, zawsze człowiek. Lista jako stała w kodzie, sama objęta deny-listą.
3. **Adwersarialny recenzent** — przed auto-apply drugie, niezależne wywołanie Claude (osobny prompt: „jesteś recenzentem bezpieczeństwa; szukaj backdoorów, osłabienia bram, eksfiltracji; odpowiedz APPROVE/REJECT+powód"). REJECT ⇒ ścieżka `/approve` z powodem w wiadomości.
4. **Canary po wdrożeniu** — po auto-apply: `py_compile` (już jest) + `respond /health` smoke; fail ⇒ automatyczny `self-repair-undo` + alert.
5. **Powiadomienie natychmiastowe** — każdy auto-apply wysyła iMessage: co zmieniono (pliki, skrót diffu), wynik canary, komenda cofnięcia. Autonomia ≠ cisza.

Wysiłek: L. Ryzyko: niskie (każda warstwa degraduje do obecnego `/approve`). Kryterium: test kontraktowy „patch dotykający `imessage_sender_allowed` z włączonym AUTO_APPLY ląduje jako pending, nie executed".

### 2b. Zadanie 1.4 (przeprojektowane): Bash zostaje pełny — twardnieje środowisko

Skoro self-repair ma naprawiać też skrypty, nie ograniczamy komend. Zamiast tego:

1. **Środowisko bez sekretów** — proces self-repair dostaje env oczyszczony z `TELEGRAM_*`, `XAI_*`, `GOOGLE_*`, `GITHUB_TOKEN/GH_*` i wskazuje pusty `AI_COUNCIL_ENV` (model nie potrzebuje sekretów do naprawy kodu; `.env` produkcyjny leży poza repo, więc kopia robocza go nie zawiera — domknąć przez env, nie tylko przez cwd).
2. **Rejestr komend** — każda komenda Bash wykonana w sesji self-repair logowana do `state/self_repair_commands.jsonl` (audytowalna historia, wejście dla recenzenta z 2a pkt 3).
3. **Post-run scan** — po sesji: diff vs pristine także dla plików **poza** repo-kopią w katalogu roboczym + ostrzeżenie, gdy log komend zawiera wzorce sieciowe (`curl`, `Invoke-WebRequest`, `ssh`) nieuzasadnione zadaniem.
4. **Uczciwa granica:** na Windowsie bez konta o obniżonych uprawnieniach to nadal nie jest sandbox — model z Bash może teoretycznie czytać dysk. Akceptowane ryzyko przy (1)+(2)+(3)+recenzencie z 2a; opcja przyszła: dedykowany user Windows / Job Object (XL, odłożone).

### 2c. Retencja pod pracę bezterminową (doprecyzowanie 2.1)

Zasada: **nic nie ginie, ale hot-path czyta tylko świeże**. Konwersacje: sharding per dzień (wzorzec `costs_file_for_day`, `ai_council.py:4765`), stare shardy po 180 dniach przenoszone do `state/archive/` (nie kasowane — to pamięć systemu); `recent_conversation` czyta od dzisiejszego sharda wstecz z early-stop. `NUDGES/IMPROVEMENTS/AUDIT_LOG`: rotacja rozmiarowa przez istniejące `rotate_state_file` (`prune_state_files`, `:4810`). `memory.sqlite` bez zmian (to pamięć trwała z założenia).

### 2d. NOWY wątek W — „Widzę, że pracujesz" (decyzja 6)

Fundament już istnieje: `start_progress_heartbeat` (`ai_council.py:2012`), `should_send_intermediate_progress` (`:2007`) — ale działa głównie dla background jobs, nie dla zwykłej odpowiedzi frontu.

| ID | Zadanie | Mechanika | Wysiłek |
|---|---|---|---|
| W1 | Telegram „pisze…" | `sendChatAction action=typing` co ~5 s w wątku pracującym nad odpowiedzią (natywny wskaźnik Telegrama, zero spamu w historii) | S |
| W2 | iMessage ACK-first | iMessage nie ma typing indicator przez AppleScript ⇒ polityka: jeśli przewidywany czas > N s (np. operator LLM/research), natychmiastowy krótki ACK („⏳ pracuję — research, ~2 min"), potem właściwa odpowiedź; ACK pomijany dla szybkich ścieżek | M |
| W3 | Heartbeat etapowy frontu | rozszerzyć heartbeat na ścieżkę respond: po przekroczeniu progu wysyłka etapu („nadal pracuję: czekam na Claude plan, 90 s") — reuse `:2007-2012`, nowy próg dla frontu | M |
| W4 | „co robisz?" → stan na żywo | komenda naturalna zwracająca: bieżący task/etap/czas trwania/PID z `progress_events` + ostatni heartbeat; działa też gdy system „mieli" | S/M |
| W5 | Watchdog ciszy | jeśli task ma heartbeat starszy niż X min, proaktywny alert „utknąłem na …" zamiast wiecznej ciszy (rozszerzenie `stuck_tasks`, `:1943`) | M |

Kolejność wdrożenia W: W1 → W2 → W4 → W3 → W5. To realizuje decyzję 6 niskim kosztem: kanały sygnalizują życie, a Bartek ma komendę kontrolną.

## 3. Zaktualizowane szybkie wygrane

Bez zmian z audytu v2 (sanityzacja mostu, ruff select, coverage, kasacje, fail-closed iMessage) **plus W1** (typing w Telegramie — kilkanaście linii, natychmiast odczuwalne) **i pozycje „usuń od ręki" z sekcji 4**.

## 4. Wyniki przeglądu deprecjacji (decyzja 5)

Metoda: AST + graf referencji na `0cc60cc`. Kluczowy wniosek: **metryka „124 zmienne single-use" z CONFIG_REFERENCE jest myląca** — zdecydowana większość to zdrowy wzorzec „jedna zmienna czytana w jednym nazwanym akcesorze" (np. `imessage_enabled` `:17141`, `self_repair_enabled` `:18621`), gdzie akcesor jest wołany wielokrotnie. **Nie deprecjonować po liczbie użyć.** Realnie martwe są tylko rzeczy poniżej.

### 4a. Martwy łańcuch LLM-routera — usunąć kod + 6 zmiennych [F]

`llm_route` (`ai_council.py:14527`, ~90 linii) wycofany z żywej ścieżki (komentarz `:15793`); `llm_router_should_try` (`:14494`) ma **zero** referencji w kodzie i testach. Zmienne do usunięcia razem z kodem: `AI_COUNCIL_LLM_ROUTER` (`:14425`), `_MODEL`, `_HISTORY_TURNS` (`:14534`), `_TIMEOUT` (`:14570`), `_MIN_CONF` (`:14590`), `_MIN_CHARS` (`:14504`). Uwaga: `llm_router_enabled` jest jeszcze pokazywany w health/status (`:5218`, `:7617`, `:17549`) — usunąć też te linie wyświetlania. Dodatkowo `AI_COUNCIL_GROK_LEGACY_ESTIMATED_COST_USD` (`:4752`) — zostawić do wygaśnięcia legacy `costs.jsonl`, potem usunąć.

### 4b. Funkcje zombie bez żadnych referencji (kod ani testy) — usunąć od ręki [F]

`source_status` (`:2336`), `verify_action` (`:12997`), `council_response` (`:13773`), `llm_router_should_try` (`:14494`). Wysiłek S, ryzyko zerowe (zero call-sites).

### 4c. Martwe w kodzie żywym, sztucznie trzymane przez testy — decyzja per pozycja [F]

| Funkcja | Linia | Diagnoza | Rekomendacja |
|---|---|---|---|
| `read_jsonl_tail` | `:757` | zastąpione przez `iter_jsonl_reverse` (M2.4) | usunąć + test |
| `poke_chat_fallback` | `:16465` | resztka sprzed L4.93 (Claude-front) | usunąć + test |
| `mail_send` + `AI_COUNCIL_MAIL_ENABLED` | `:17177`, `:17174` | kanał mail nigdy nie wpięty w żywą ścieżkę | usunąć albo świadomie wpiąć — decyzja produktowa |
| `apple_date_to_unix`, `imessage_message_text`, `imessage_is_assistant_echo`, `imessage_drain_rows` | `:17260-17505` | host-side czytanie chat.db — osierocone po M2.3 (most przeniesiony do standalone skryptu na Macu) | usunąć z hosta; logika żyje w `scripts/mac_imessage_bridge_standalone.py` |

Po usunięciu skasować też odpowiadające testy (one „pokrywają" martwy kod i zawyżają poczucie pokrycia).

### 4d. Czego NIE ruszać

Pozostałe ~115 zmiennych single-use to żywe akcesory konfiguracyjne — koszt ich „sprzątania" przewyższa zysk, a CONFIG_REFERENCE.md dokumentuje je automatycznie. Flagi per-feature (`AI_COUNCIL_WATCH_DIGEST`, `AI_COUNCIL_FACT_AUTO_EXTRACT` itd.) zostają: to wyłączniki operacyjne, nie dług.

**Łączny efekt sprzątania 4a-4c: ~350-450 linii kodu i 8-10 zmiennych mniej, zero zmiany zachowania.** Sugerowany pakiet: jeden commit „L4.x dead code sweep" z pełnym pytest przed/po.

## 5. Kolejność wykonania (po decyzjach)

1. **Sprint A (szybkie):** 4b + 4a (sweep martwego kodu) · sanityzacja mostu (1.2) · ruff select (2.5) · coverage report (0.1) · **W1 typing Telegram**.
2. **Sprint B (bezpieczeństwo autonomii):** strażnicy AUTO_APPLY (2a) · hartowanie środowiska Bash (2b) · fail-closed iMessage (1.1) · silent excepts → record_error (1.5).
3. **Sprint C (życie bezterminowe + widoczność):** retencja/sharding konwersacji (2c) · W2-W5 · testy charakterystyczne listen_once (0.2).
4. **Sprint D (szwy monolitu):** rejestr `build_response` (2.2) · `route_text` (2.3) · scalenie ścieżek subprocess Claude (3.2).

Każdy sprint kończy się pełnym pytest na Mac + (po approval) deploy z backupem wg dyscypliny z CLAUDE.md.
