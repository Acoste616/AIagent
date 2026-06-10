# Pełny Audyt Repozytorium — 2026-06-10 (v2, wieczorny)

Audytor: Claude (Fable 5). Zakres: cały working tree na stanie commitu `0cc60cc` (L4.102), Mac checkout.
Metoda: analiza statyczna AST + przegląd ręczny + trzy równoległe głębokie przejścia (architektura/jakość, bezpieczeństwo, testy/ops/docs). Każde twierdzenie ma `plik:linia`. Oznaczenia: **[F]** fakt zweryfikowany w kodzie, **[O]** ocena/wniosek. Żaden kod nie był modyfikowany.

Uzupełnia (nie powtarza) poranny `docs/audit/REPO_AUDIT_2026-06-10.md` — sprawdziłem jego status: M0–M3 wykonane (CI istnieje, dispatch registry istnieje, cost sharding działa, testy podzielone), z dwoma resztkami: `docs/.DS_Store` nadal w git, a `latest_by_id` nadal czyta cały plik.

---

## 1. Streszczenie Wykonawcze

Ocena ogólna: **B-**. Jak na jednoosobowy, intensywnie rozwijany system agentowy, repo jest w zaskakująco dobrej formie: 551 testów behawioralnych, CI na dwóch OS-ach, zero zależności zewnętrznych, produkcyjnej klasy walidacja ścieżek (`safe_resolve`), bramy approval z poziomami ryzyka i konsekwentna dokumentacja per-warstwa. Ocenę obniżają trzy rzeczy. Po pierwsze, granice zaufania na kanałach wejściowych nie są fail-closed: pusty allowlist iMessage oznacza tryb otwarty (`ai_council.py:17444-17446`), a most na Macu wstrzykuje niewalidowane `msg_id` do zdalnego PowerShella (`scripts/mac_imessage_bridge_standalone.py:57-60,85`). Po drugie, flaga `AI_COUNCIL_SELF_REPAIR_AUTO_APPLY` pozwala wdrożyć kod napisany przez LLM do produkcji bez człowieka — domyślnie wyłączona, ale to najgroźniejszy pojedynczy przełącznik w systemie (`ai_council.py:19057-19062`). Po trzecie, monolit 19 315 linii / 770 funkcji rośnie szybciej, niż powstają w nim szwy: `build_response` to 60-gałęziowy megaswitch, a kilka plików stanu (konwersacje, nudges, audit) rośnie bez retencji i jest czytanych w całości przy każdej wiadomości. Trzy główne ryzyka: (1) łańcuch prompt-injection → akcja przy otwartych/niedokręconych bramach kanałów, (2) cicha utrata danych w 11 miejscach `except Exception: pass`, w tym audit log i tury konwersacji, (3) degradacja wydajności i czytelności wraz ze wzrostem plików stanu i samego monolitu. Trzy główne okazje: (1) tani fail-closed na kanałach + sanityzacja mostu (kilka godzin pracy, zamyka najgorsze scenariusze), (2) powielenie istniejącego, świetnego wzorca `NATURAL_INTENT_RULE_GROUPS` na `build_response`/`route_text`/`approve_response`, (3) włączenie reguł ruff i retencji stanu — dwie zmiany, które będą procentować przy każdym kolejnym sprincie.

---

## 2. Mapa Repo

**Cel:** prywatny „Agent OS" Bartka — klon Poke z ambicją przewyższenia go: Telegram + iMessage jako kanały, Claude (głos/plan), Grok (research/fallback), Codex (worker), pamięć, recipes, akcje za approval, pętla self-repair. Jeden użytkownik, produkcja na Windows (`D:\ai-council`), most iMessage na Macu. Poziom dojrzałości: **zaawansowane narzędzie osobiste w fazie szybkiej iteracji** — nie biblioteka, nie usługa wielodostępna.

**Stack [F]:** Python 3.10+, wyłącznie stdlib (`ai_council.py:4-31` — zero importów third-party). Testy: pytest (551 testów wg zliczenia, CLAUDE.md mówi 540/548 — drobny dryf). Lint: ruff (tylko `line-length`). CI: GitHub Actions, ubuntu+windows, Python 3.10 (`.github/workflows/ci.yml`).

**Architektura (szkic przepływu):**

```
Telegram getUpdates ─┐                            ┌─ Claude CLI (subprocess)
iMessage bridge ─────┤→ listen_once (L18282)      ├─ Grok API (urlopen)
  (Mac, SSH, 15s)    │   → route_text (L15808)    ├─ Codex CLI (worker pack)
Shortcuts HTTP ──────┘   → natural_intent_route   │
  (L4299, token)         → build_response (L17852)┴→ pending actions (R0/R1/R2)
                              │                        → /approve → executors
                         state/*.jsonl + memory.sqlite + recipes + background jobs
```

**Kluczowe katalogi:**

| Ścieżka | Opis |
|---|---|
| `ai_council.py` | Cały system: 19 315 linii, 770 funkcji top-level, 4 klasy |
| `tests/` | 11 plików domenowych, ~10,5k linii, hermetyczny `conftest.py` |
| `scripts/mac_imessage_bridge_standalone.py` | Kanoniczny most iMessage (Mac, LaunchAgent) — **0 testów** |
| `scripts/deploy/`, `windows-deploy/` | Ręczny deploy przez SSH/PowerShell |
| `docs/implementation/` (93 pliki), `docs/handoffs/`, `docs/audit/` | Wyjątkowa jak na solo projekt dyscyplina dokumentacyjna |
| `docs/operations/CONFIG_REFERENCE.md` | Auto-generowany inwentarz 167 env vars |
| `artifacts/task-*/` | Artefakty taskow — niewersjonowane (git ls-files puste) ✓ |

**Co mnie zaskoczyło:** (a) zero zależności — to świadoma i bardzo dobra decyzja dla deploy „skopiuj 1 plik"; (b) `NATURAL_INTENT_RULE_GROUPS` (`ai_council.py:15362-15382`) to wzorcowy szew architektoniczny, którego reszta routingu nie dostała; (c) wzorzec sidecar+reconcile w `BlockingFileLock`/`append_jsonl` (`ai_council.py:693-712, 823-841`) jest solidniejszy niż w wielu komercyjnych projektach; (d) numer telefonu i e-mail allowlisty są zapisane w `CLAUDE.md` commitowanym do GitHuba — patrz Otwarte Pytania.

---

## 3. Raport Audytu

### 3.1 Bezpieczeństwo (najbrzydsze części — czytaj najpierw)

**S1 — `AI_COUNCIL_SELF_REPAIR_AUTO_APPLY`: kod autorstwa LLM trafia do produkcji bez człowieka.**
(a/b) `ai_council.py:18843-18847` (definicja flagi) i `19057-19062` (auto-approve + `execute_self_repair_action`). [F]
(c) Gdy flaga ON: Claude z pełnymi narzędziami Read/Write/Edit/**Bash** generuje patch w izolowanej kopii; zielony pytest ⇒ patch ląduje w produkcyjnym `ai_council.py`. Pytest przejdzie także dla złośliwej zmiany, która nie psuje istniejących testów (np. usunięcie checku allowlisty, eksfiltracja w gałęzi nieobjętej testem). Wejściem do self-repair są błędy z `errors.jsonl` — czyli treść częściowo kontrolowalna z zewnątrz (wiadomości, wyniki researchu). To pełny łańcuch prompt-injection → kod w produkcji.
(d) **Krytyczna przy włączonej fladze; Średnia przy domyślnym OFF** (default `False` to dobra decyzja, ale flaga istnieje i jest udokumentowana jako feature).

**S2 — iMessage: pusty allowlist = tryb otwarty, bez ostrzeżenia.**
(a/b) `imessage_sender_allowed`, `ai_council.py:17441-17447`: `if not allowed: return True, "open"`. [F]
(c) Brak/utrata env var `AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS` (świeża maszyna, regresja `.env`, literówka w nazwie — `cfg()` zwraca `""` po cichu) ⇒ każdy, czyja wiadomość dotrze przez most, przechodzi przez pełny routing łącznie z tworzeniem akcji. W produkcji allowlist jest dziś ustawiony (CLAUDE.md), więc ekspozycja bieżąca jest niska — ale projekt jest fail-open, a startup niczego nie sygnalizuje.
(d) **Wysoka** (projektowo), bieżąco zmitigowana konfiguracją.

**S3 — Most Mac: niewalidowane `msg_id`/`status` interpolowane do zdalnego PowerShella.**
(a/b) `scripts/mac_imessage_bridge_standalone.py:57-60` (`_host_cmd` buduje `powershell -Command "{inner}"` f-stringiem) i `:85` (`ack()` wstawia `msg_id` z JSON-a zwróconego przez hosta). [F]
(c) `msg_id` pochodzi z `imessage-outbox-dump` na Windowsie. Jeśli host (lub kanał SSH) zwróci spreparowane `msg_id` z metaznakami PowerShella (`";`, `$(...)`), Mac wykona dowolny PowerShell z powrotem na Windowsie. Dziś to eskalacja „skompromitowany host ⇒ ponowna egzekucja", ale to także krucha poprawność (każdy przyszły format ID z `"` psuje komendę — komentarz przy `--detail` w `:79-83` pokazuje, że ten problem już raz ugryzł). Dla kontrastu: `b64` jest bezpieczne alfabetem, a `--sender` przechodzi przez `_safe_handle` (`[A-Za-z0-9@.+_-]`, max 64) — czyli wzorzec sanityzacji już istnieje, tylko `msg_id`/`status`/`HOST_DIR`/`HOST_PY` go nie dostały.
(d) **Wysoka**.

**S4 — Self-repair: narzędzie Bash bez sandboxa na poziomie OS.**
(a/b) Kontrakt narzędzi self-repair, `ai_council.py:18853` i okolice. [F]
(c) „Izolacja" to kopia katalogu (konwencja cwd), nie sandbox. Model w fazie „naprawy" może Bashem czytać `~/.config/ai-council/.env`, wykonywać połączenia sieciowe, pisać poza kopią. Nawet przy ręcznym `/approve` finalnego patcha, side-effecty Bash wykonują się już podczas samej diagnozy/weryfikacji.
(d) **Wysoka** (Krytyczna w połączeniu z S1).

**S5 — `HOST_DIR`/`HOST_PY` niecytowane w komendzie PowerShell.** `mac_imessage_bridge_standalone.py:57-58`. [F] Ścieżka ze spacją łamie komendę; wartości z env nie są sanityzowane. **Średnia** (głównie poprawność).

**S6 — `/health` i `/` serwera Shortcuts odpowiadają bez tokena** (`ai_council.py:4303-4312`), ujawniając wersję/serwis. Przy domyślnym bindzie `127.0.0.1` znaczenie małe. **Niska**.

**Mocne strony bezpieczeństwa [F]:** `hmac.compare_digest` dla tokena Shortcuts (`ai_council.py:4278-4285`); zero `shell=True` we wszystkich 46 użyciach subprocess; `safe_resolve` z normalizacją NFKC, odrzuceniem `..`, nazw urządzeń Windows, kontrolą reparse-points i finalnym `os.realpath` (`ai_council.py:8428-8477`) — klasa produkcyjna; SQL wyłącznie parametryzowany (jedyny f-string DDL na stałych literalach, `ai_council.py:7680`); `.env` poza repo (`ai_council.py:52`), brak sekretów w `artifacts/`; auth przed odczytem body i limit rozmiaru w handlerze HTTP (`ai_council.py:4322-4340`); `redact_secrets` stosowany na ścieżkach błędów; serwer Shortcuts odmawia startu bez tokena (`ai_council.py:4344-4347`).

### 3.2 Architektura i projektowanie

**A1 — Brak jakichkolwiek wymuszalnych granic modułów.** [F] 19 315 linii w płaskiej przestrzeni nazw; „sekcje" istnieją tylko jako konwencja pozycji w pliku. Konkretne przecieki warstw: scheduler recipes woła bezpośrednio wysyłkę Telegrama i czyta config kanału (`run_due_recipes`, `ai_council.py:6432`); `approve_response` (`:10906`) łączy logikę stanu approval, budowę stringów odpowiedzi, persystencję JSONL, wykonanie na FS i zapis pamięci; `listen_once` (`:18282`, 224 linie, 66 rozgałęzień) inline'uje poll, offset, idempotencję, routing, wysyłkę, persystencję, audit i nudges. **Wysoka** [O — konsekwencja: każda zmiana persystencji/kanału wymaga czytania pełnego grafu wywołań].

**A2 — God-funkcje bez szwów.** [F] `route_text` (`:15808`, 182 linie, 99 rozgałęzień, czyste prefix-dispatch — najłatwiejsze do tablicy), `build_response` (`:17852`, 187 linii, ~60 gałęzi `command ==`, w tym inline'owy `@all` odpalający 3 CLI synchronicznie przy `:18019`), `run_background_job` (`:13506`, 4× powtórzony guard `send_progress and chat_id`). Wzorzec docelowy już istnieje w repo: `NATURAL_INTENT_RULE_GROUPS` (`:15362-15382`). **Wysoka**.

**A3 — Config sprawl bez walidacji startowej.** [F] 167-172 zmienne `AI_COUNCIL_*`; `cfg()` (`:524`) zwraca `""` dla każdej literówki bez ostrzeżenia; defaulty rozsiane po call-site'ach; `REQUIRED_KEYS` (`:84`) sprawdzane tylko w podkomendzie `env`. `CONFIG_REFERENCE.md` istnieje i wykazuje 124 zmienne jednorazowego użycia. To bezpośrednia przyczyna ryzyka S2 (fail-open przez brak klucza). **Wysoka**.

**A4 — Martwy kod: `llm_route`.** [F] `:14527`, ~90 linii wykonujących płatne wywołanie Groka; komentarz `:15793` mówi wprost „RETIRED from the live path"; zero żywych wywołań. **Średnia** (myli czytelnika i kusi regresją kosztową).

**A5 — `control.json` bez locka.** [F] `load_control`/`save_control` to zwykły read/write JSON (okolice `:68`), bez `BlockingFileLock`, którym chronione są JSONL-e. Torn write możliwy przy zbiegu listener + background worker. Dla kontrastu `write_offset` jest już atomowe (temp + `os.replace`, `:14001-14006`) — wzorzec do skopiowania. **Średnia**.

**A6 — `/workspace` zwraca zahardkodowane `D:\ai-council`** ignorując `PROJECT_DIR` (`:17879-17881`). Na Macu zawsze kłamie. **Średnia/Niska**.

### 3.3 Jakość kodu

**Q1 — 11 z 34 bloków `except Exception` połyka błędy bez śladu.** [F] Najgorsze: zrzucenie zdarzenia **audit** z `pass` (`ai_council.py:8396-8399` — luka w ścieżce decyzji workspace-hands, czyli dokładnie tam, gdzie audit jest najcenniejszy); cicha utrata tury konwersacji użytkownika mimo komentarza L4.64 „can never drop it" (`:18427-18431`); cicho gubiony order_handoff — użytkownik dostaje odpowiedź czatu, ale przycisk approve nigdy nie powstaje (`:17076-17077`); ciche pominięcie ekstrakcji faktów (`:8237-8238`); cicho niesapisany artefakt (`:17723-17724`). Inne bloki robią to dobrze (`record_error` np. `:13640`, `:17494`). **Wysoka** — to systemowa niespójność, nie pojedynczy bug.

**Q2 — Duplikacja ścieżek subprocess Claude.** [F] `poke_chat_claude_response` (`:16718-16748`) i `brain_claude_response` (`:16894-16937`) to ~40-liniowe bliźniaki (budowa komendy, timeout, FileNotFoundError, finalize, record_error), mimo że generyczny `run_operator_subprocess` (`:16018-16084`) już obsługuje dokładnie ten wzorzec. **Średnia**.

**Q3 — Drobna duplikacja:** idiom `split(maxsplit=1)` ×5 w 35 liniach `route_text` (`:15857-15892`); trzy niemal identyczne stringi „Approved + executed" w `approve_response` (`:10921-10945`); guard anulowania ×4 w `run_background_job`. **Niska**.

**Q4 — 18 stałych `*_VERSION = "L4.xx"`** (`:251-270`) wstrzykiwanych do promptów LLM zamiast jednego `__version__`. **Niska** [O].

### 3.4 Testowanie

**T1 — Jakość istniejących testów jest wysoka.** [F] Testy asercjonują zachowanie (treść odpowiedzi, pola route'a, wiersze JSONL w tmp), nie sam brak wyjątku — np. `tests/test_council_routing.py:26-59` sprawdza 12 właściwości odpowiedzi. `test_routing_contract.py` to 57 złotych tras bez mocków. `conftest.py` neutralizuje 6 katalogów, 14 flag, 5 sekretów i allowlist iMessage. Zero `time.sleep`, zero zależności kolejności. To realna siatka bezpieczeństwa.

**T2 — Luki pokrycia w punktach wejścia.** [F] `listen_once` testowany tylko na happy-path jednego update'a (`tests/test_council_memory_state.py:831`) — brak testów pustej paczki, zepsutego JSON-a, awarii zapisu offsetu, okna idempotencji; pełna ścieżka HTTP `/shortcut` z tokenem testowana tylko przez bezpośrednie wywołanie `process_shortcut_payload` (middleware tokenowy poza testem integracyjnym HTTP); `scripts/mac_imessage_bridge_standalone.py` — **zero testów** mimo rangi kanonicznego mostu. Brak jakiegokolwiek pomiaru coverage (brak `pytest-cov`). **Średnia/Wysoka** [O — bo to dokładnie komponenty na granicy zaufania].

**T3 — Smelle testowe.** [F] 20+ zduplikowanych inline'owych `fake_cfg` w 5 plikach; łańcuchy 12-14 `patch.object` per test (np. `test_council_memory_state.py:854-868`) — pochodna stałych modułowych; `test_council_proactive_jobs.py` nadal 4 942 linie / 180 testów o heterogenicznej tematyce. **Średnia**.

### 3.5 Wydajność

**P1 — `recent_conversation` czyta cały `CONVERSATIONS_FILE` przy każdej wiadomości i plik nie ma retencji.** [F] `ai_council.py:1018-1021` (pełny `read_jsonl` + filtr w Pythonie); wywołania m.in. `:16604`, `:16964` — czyli ścieżka każdej rozmowy LLM. `prune_state_files` (`:4810-4835`) rotuje tylko progress_events i errors; `CONVERSATIONS_FILE`, `NUDGES_FILE`, `IMPROVEMENTS_FILE`, `ACTIONS_FILE`, `AUDIT_LOG` rosną bez ograniczeń. Każda wiadomość = 2 wiersze; po miesiącach pracy to liniowo rosnąca latencja każdej odpowiedzi. Wzorzec naprawy (`iter_jsonl_reverse`, `:729`) już istnieje i jest użyty w `get_latest_task` (`:1555`). **Wysoka**.

**P2 — `latest_by_id` nadal czyta cały plik** (`:1490-1500`, wołane z `latest_tasks` `:1562`) — resztka po M2.4. **Średnia**.

**P3 — `nudged_ids()`/`nudge_keys()` pełny odczyt `NUDGES_FILE` w każdym cyklu poll** (`:10008,10012`). **Średnia**.

**Zdrowe:** cost ledger shardowany per dzień z legacy fallback (`:4765`, `:4885-4896`); `usage_today` O(1 dnia); sqlite per-call jest OK przy tej skali [O]; interwał mostu 15 s adekwatny.

### 3.6 Zależności

Zdrowe — jedno zdanie: zero pakietów third-party w runtime [F, `ai_council.py:4-31`], CI instaluje tylko pytest+ruff; jedyna uwaga to brak zadeklarowanego `requires-python = ">=3.10"` w `pyproject.toml` mimo użycia składni 3.10+ (`list[dict]`, `X | None`). **Niska**.

### 3.7 DevEx i operacje

**D1 — Ruff działa na domyślnych regułach.** [F] `pyproject.toml:5-7` ma tylko `line-length = 120` — bez `select` lint nie łapie m.in. bugbearów (B), bezpieczeństwa (S), niełapanych wyjątków. Najtańsza dźwignia jakości w repo. **Wysoka** [O].

**D2 — CI: jedna wersja Pythona (3.10), brak coverage, brak etapu smoke po deployu.** [F] `.github/workflows/ci.yml:20`. **Średnia**.

**D3 — Brak type-checkera.** [F] ~97% funkcji ma adnotacje zwrotów (świetna baza), ale nic ich nie weryfikuje. **Średnia**.

**D4 — Taksonomia błędów niespójna.** [F] `record_error` (`:844`) przyjmuje `severity`, ale wywołania są niespójne; `actionable_error_rows` (`:885`) filtruje szum ad hoc. Stąd „errors_24h ≈ 50, mostly benign" z CLAUDE.md — szum zjada sygnał, a errors.jsonl jest wejściem do self-repair (sprzężenie z S1). **Średnia**.

**D5 — Higiena:** `docs/.DS_Store` nadal śledzony (jedyny taki artefakt; `git ls-files` potwierdza), brak `.DS_Store` w `.gitignore`; brak pre-commit. **Niska**.

### 3.8 Dokumentacja

Zdrowa — wyróżniająca się. README z poprawnymi komendami, 93 doki implementacyjne, handoffy, auto-generowany `CONFIG_REFERENCE.md` (167 zmiennych), `.env.example` w `docs/operations/`. Jedyne uwagi: dryf liczników testów w CLAUDE.md (540/548 vs 551 policzonych) i brak jednego liniowego przewodnika „świeża maszyna od zera" (wiedza rozproszona po CLAUDE.md/README/scripts). **Niska**.

### 3.9 Mocne Strony (do zachowania)

Zero zależności (deploy = 1 plik) · `safe_resolve` klasy produkcyjnej · wzorzec lock+sidecar+reconcile dla JSONL · `NATURAL_INTENT_RULE_GROUPS` jako gotowy wzorzec szwu · bramy ryzyka R0/R1/R2 z `/approve`, `/undo`, backupami i `self-repair-undo` · domyślne OFF dla auto-apply · 551 testów behawioralnych + golden routing contract + hermetyczny conftest · CI na 2 OS · `redact_secrets` i brak sekretów w repo · dyscyplina dokumentacyjna per-warstwa.

---

## 4. Strategia Poprawy

**Temat 1: Granice zaufania mają być fail-closed (wyjaśnia S1-S5, A3-częściowo, D4).**
Stan docelowy: żaden kanał wejściowy nie działa w trybie otwartym przez brak konfiguracji; wszystko, co przekracza granicę proces↔proces (SSH/PowerShell), jest sanityzowane wzorcem `_safe_handle`; self-repair ma twardy kontrakt: Bash tylko do pytest, a auto-apply usunięte albo obwarowane drugim, niezależnym warunkiem. Zasada: *brak konfiguracji = odmowa, nie zgoda; treść z zewnątrz nigdy nie skleja komend.*

**Temat 2: Awaria zostawia dowód (wyjaśnia Q1, D4).**
Stan docelowy: zero `except Exception: pass` na ścieżkach danych (audit, konwersacje, akcje, artefakty) — każdy łyk wyjątku przechodzi przez `record_error` z ujednoliconą severity (`error|warning|noise`); `actionable_error_rows` filtruje po taksonomii, nie po heurystykach. To podnosi też jakość wejścia do self-repair. Zasada: *cisza jest najdroższym trybem awarii w systemie autonomicznym.*

**Temat 3: Stan ma retencję i odczyt od ogona (wyjaśnia P1-P3).**
Stan docelowy: każdy plik w `state/` ma zadeklarowaną politykę retencji w `prune_state_files`, a hot-path nigdy nie czyta pliku w całości — `iter_jsonl_reverse` z early-stop wszędzie tam, gdzie dziś `read_jsonl(...)[-n:]`. Zasada: *system pomyślany na miesiące pracy nie może mieć O(historia) w pętli wiadomości.*

**Temat 4: Monolit dostaje szwy, nie rozbiórkę (wyjaśnia A1, A2, Q2-Q3).**
Stan docelowy: `build_response`, `route_text` i `approve_response` stają się rejestrami dyspatchu na wzór `NATURAL_INTENT_RULE_GROUPS`; duplikaty subprocess scalają się w `run_operator_subprocess`. Świadomie **nie** rekomenduję podziału na pakiet modułów: jednoplikowość to realna wartość operacyjna (deploy, self-repair na kopii, brak importów), a koszt/ryzyko pełnej modularizacji przy obecnej dojrzałości przewyższa zysk. Zasada: *granice przez rejestry i konwencję testowaną kontraktami, nie przez pliki.*

**Temat 5: Bramy jakości pracują za Ciebie (wyjaśnia D1-D3, T2).**
Stan docelowy: ruff z `select = ["E","F","B","S","G","UP"]` (z punktowymi ignore), pomiar coverage w CI (najpierw raport, próg później), matryca Pythona 3.10+3.12, testy charakterystyczne dla `listen_once` i ścieżki tokenowej HTTP.

**Czego świadomie NIE naprawiać:** pełna modularizacja na pakiety (XL, ryzyko deploy/self-repair, mały zysk dziś); wymiana JSONL/sqlite na „prawdziwą bazę" (obecny wzorzec lock+sidecar jest adekwatny do skali 1 użytkownika); przepisanie na async (polling 15-60 s nie potrzebuje async); pooling połączeń sqlite (nie jest wąskim gardłem); czyszczenie 124 jednorazowych env vars hurtem (deprecjonować przy okazji dotykania danego kodu); 18 stałych `*_VERSION` (kosmetyka).

**Definicja „zrobione" (mierzalne):** (1) `imessage_sender_allowed` bez gałęzi `"open"` lub z wymaganym jawnym opt-in + test kontraktowy; (2) grep `except Exception:\n\s+pass` na ścieżkach audit/konwersacje/akcje = 0 trafień; (3) `read_jsonl(CONVERSATIONS_FILE|NUDGES_FILE|TASKS_FILE)` poza narzędziami administracyjnymi = 0 trafień w hot-path; (4) CI czerwone przy naruszeniu reguł ruff B/S; (5) coverage raportowany w każdym runie CI; (6) most iMessage: wszystkie wartości interpolowane do `_host_cmd` przechodzą walidację wzorcem; (7) zero znalezisk Krytycznych i Wysokich z tego raportu otwartych.

---

## 5. Plan Zadań

### Kamień 0 — Sieć bezpieczeństwa (przed refaktorami)

| ID | Zadanie | Pliki | Kryteria akceptacji | Wysiłek | Ryzyko | Zależy od |
|---|---|---|---|---|---|---|
| 0.1 | Coverage w CI (raport, bez progu): `pip install pytest-cov`, `--cov=ai_council --cov-report=term` | `.github/workflows/ci.yml` | CI wypisuje % pokrycia; znamy bazę | S | zerowe | — |
| 0.2 | Testy charakterystyczne `listen_once`: pusta paczka, zepsuty update, okno idempotencji, awaria zapisu offsetu | `tests/test_council_memory_state.py` | 4+ nowe testy zielone, utrwalają obecne zachowanie | M | niskie | — |
| 0.3 | Test integracyjny HTTP `/shortcut` z tokenem (poprawny/zły/brak) przez prawdziwy `ThreadingHTTPServer` | `tests/test_council_proactive_jobs.py` (wzorzec już jest: `:4030-4044`) | 3 testy: 200/401/401 | S | zerowe | — |
| 0.4 | Smoke-testy mostu: import modułu, `_safe_handle`, `_host_cmd` (kształt komendy), parsowanie pull/ack na fixture'ach | nowy `tests/test_imessage_bridge_script.py` | most ma >0 testów; CI je uruchamia | M | zerowe | — |

### Kamień 1 — Krytyczne poprawki (bezpieczeństwo i poprawność)

| ID | Zadanie | Pliki | Kryteria akceptacji | Wysiłek | Ryzyko | Zależy od |
|---|---|---|---|---|---|---|
| 1.1 | **Fail-closed iMessage**: gałąź `"open"` → odmowa + `record_error("imessage_config", severity="error")`; opcjonalny jawny opt-in `AI_COUNCIL_IMESSAGE_ALLOW_OPEN=true` na czas migracji | `ai_council.py:17441-17447`, testy kontraktowe | pusty allowlist ⇒ deny; test; doctor ostrzega | S | średnie (może uciszyć kanał przy złej konfiguracji — stąd wpis w doctor) | 0.2 |
| 1.2 | **Sanityzacja mostu**: `msg_id`/`status` przez walidację `^[A-Za-z0-9._-]{1,64}$` (odrzuć i zaloguj), `HOST_DIR`/`HOST_PY` walidowane przy starcie | `scripts/mac_imessage_bridge_standalone.py:57-60,85` | zła wartość ⇒ ack pominięty + log, nie egzekucja; testy z 0.4 pokrywają | S | niskie | 0.4 |
| 1.3 | **Decyzja AUTO_APPLY**: usunąć flagę albo dodać drugi niezależny warunek (np. patch dotyka tylko plików z allowlisty + limit rozmiaru diffu + zakaz dotykania funkcji bezpieczeństwa po nazwach) | `ai_council.py:18843-18847,19057-19062` | flaga usunięta lub guard z testami; doc zaktualizowany | M | niskie (feature i tak OFF) | — |
| 1.4 | **Kontrakt Bash w self-repair**: ograniczyć Bash do komend pytest/py_compile (walidacja po stronie hosta, nie tylko prompt), albo wyłączyć Bash i uruchamiać pytest samemu po zwrocie patcha | `ai_council.py:18853+` | model nie może wykonać dowolnego Basha podczas naprawy; testy | M/L | średnie (może obniżyć skuteczność napraw) | 1.3 |
| 1.5 | **Cisza → dowód**: 11 silent excepts dostaje `record_error` (audit `:8396`, conversation turn `:18427`, order_handoff `:17076`, fakty `:8237`, artefakty `:17723`, pozostałe wg listy Q1) | `ai_council.py` | grep-kryterium z sekcji 4; testy na 2-3 reprezentatywnych | M | niskie | — |

### Kamień 2 — Wysoka dźwignia

| ID | Zadanie | Pliki | Kryteria akceptacji | Wysiłek | Ryzyko | Zależy od |
|---|---|---|---|---|---|---|
| 2.1 | Retencja + odczyt od ogona: `recent_conversation`, `latest_by_id`, `nudged_ids`/`nudge_keys` na `iter_jsonl_reverse` z early-stop; `CONVERSATIONS/NUDGES/IMPROVEMENTS/AUDIT` w `prune_state_files` | `ai_council.py:1018-1021,1490-1500,10008-10012,4810-4835` | brak pełnych odczytów w hot-path (grep-kryterium); testy retencji na wzór cost shards | M | średnie (semantyka „ostatnich N" musi być identyczna — testy charakterystyczne najpierw) | 0.2 |
| 2.2 | `build_response` → rejestr `COMMAND_HANDLERS: dict[str, Callable]`; `@all` do osobnej funkcji | `ai_council.py:17852-18038` | dispatcher <20 linii; golden routing contract zielony bez zmian | L | średnie | 0.1-0.3 |
| 2.3 | `route_text` → tablica prefiksów (analogicznie) | `ai_council.py:15808+` | jak wyżej; `test_routing_contract.py` bez zmian | M | niskie | 2.2 |
| 2.4 | Walidacja configu w `doctor` + starcie: nieznane klucze `AI_COUNCIL_*` w env ⇒ warning; `REQUIRED_KEYS` sprawdzane przy `serve` | `ai_council.py:437-530,84` | literówka w nazwie zmiennej jest wykrywalna; test | M | niskie | — |
| 2.5 | Ruff `select = ["E","F","B","S","G","UP"]` + punktowe `ignore`/`per-file-ignores` (testy: S101); naprawa znalezisk | `pyproject.toml`, drobne poprawki w kodzie | CI czerwone na B/S; zero nowych wyłączeń bez komentarza | M | niskie | — |
| 2.6 | CI: matryca 3.10+3.12, `requires-python=">=3.10"` | `.github/workflows/ci.yml`, `pyproject.toml` | zielone na obu wersjach | S | niskie | — |

### Kamień 3 — Jakość i dopracowanie

| ID | Zadanie | Pliki | Kryteria | Wysiłek | Ryzyko |
|---|---|---|---|---|---|
| 3.1 | Usunąć `llm_route` (martwy, `:14527`) | `ai_council.py` | grep `llm_route(` = tylko historia w docs | S | zerowe |
| 3.2 | Scalić `poke_chat_claude_response`/`brain_claude_response` na `run_operator_subprocess` | `:16718,:16894,:16018` | jedna ścieżka subprocess Claude; testy operatorów zielone | M | średnie |
| 3.3 | Wspólna fabryka `fake_cfg` + helper patchowania stanu w `council_test_shared.py` | `tests/` | brak inline `fake_cfg` w nowych testach; stare migrowane przy okazji | M | niskie |
| 3.4 | `approve_response`: dispatch typu akcji + wspólny formatter odpowiedzi | `:10906-11050` | 7 gałęzi → rejestr; testy bez zmian | M | niskie |
| 3.5 | `/workspace` z `PROJECT_DIR` (`:17879-17881`); `.DS_Store` z gita + wpis `.gitignore`; dryf liczników w CLAUDE.md; lock/atomic write dla `control.json` (wzorzec z `write_offset`) | różne | oczywiste | S | zerowe |
| 3.6 | Taksonomia `severity` (`error|warning|noise`) w `record_error` + przegląd call-site'ów; `actionable_error_rows` filtruje po niej | `:844,:885` | errors_24h pokazuje tylko `error`; szum sklasyfikowany | M | niskie |
| 3.7 | Split `test_council_proactive_jobs.py` (4 942 linii) na 2-3 pliki tematyczne | `tests/` | żaden plik testowy >2 500 linii | M | zerowe |

### Szybkie wygrane (zrób od ręki, wszystkie S, wysoki wpływ)

1. **1.2** sanityzacja `msg_id` w moście (kilkanaście linii, zamyka High),
2. **2.5-lite** sam wpis `select` do ruff i przegląd co krzyczy,
3. **0.1** coverage report w CI,
4. **3.1** kasacja `llm_route`,
5. **3.5** `.DS_Store` + `/workspace` + gitignore,
6. **1.1** fail-closed iMessage (jeśli akceptujesz wpis migracyjny w doctor).

### Szkice implementacji — top 3

**1.1 Fail-closed iMessage.** W `imessage_sender_allowed` zamienić `return True, "open"` na: jeśli `bool_cfg("AI_COUNCIL_IMESSAGE_ALLOW_OPEN", False)` → `(True, "open_explicit")`, w przeciwnym razie `record_error("imessage_config", "allowlist empty -> deny", severity="error")` i `(False, "denied_no_allowlist")`. Dodać linijkę do `doctor` (status allowlisty). Pułapki: produkcja ma już allowlist, ale **most na Macu i testy konfiguracji trzeba sprawdzić przed deployem**, żeby nie uciszyć kanału; conftest już resetuje allowlist — testy, które polegały na trybie open, trzeba zaktualizować świadomie (to one dokumentują zmianę kontraktu).

**2.1 Retencja konwersacji + odczyt od ogona.** Krok 1: test charakterystyczny utrwalający dokładny wynik `recent_conversation` (kolejność, limit, filtr chat_hash) na fixture 50+ wierszy. Krok 2: implementacja przez `iter_jsonl_reverse(CONVERSATIONS_FILE)` ze zbieraniem do `limit` pasujących i odwróceniem na końcu. Krok 3: retencja — najprościej shard per dzień jak `costs-YYYY-MM-DD.jsonl` (wzorzec `costs_file_for_day` `:4765` + legacy fallback), albo rotacja w `prune_state_files`. Pułapka: `conversation_liveness` i inne czytelniki tego pliku (`:1000,:1038,:14534`) muszą przejść na ten sam dostęp; sharding zmienia ścieżki — fallback na legacy plik obowiązkowy jak przy kosztach.

**2.2 `build_response` jako rejestr.** Mechanika: `COMMAND_HANDLERS: dict[str, Callable[[str, dict], str]]` budowany raz; handlery przyjmują `(prompt, route)`; istniejące `if command == "/x":` przenosić blokami 1:1 do funkcji `_cmd_x` bez zmiany treści (czysty mechaniczny lift). Gałęzie wymagające dodatkowego kontekstu (`chat_id`, `send_progress`) dostają go przez `route`. `@all` (`:18019`) wydzielić najpierw — to jedyny blok z własnym I/O wielooperatorowym. Weryfikacja: `test_routing_contract.py` + pełny pytest muszą przejść **bez żadnej zmiany w testach** — jeśli test wymaga zmiany, to nie był lift 1:1. Pułapka: kolejność gałęzi ma znaczenie tylko tam, gdzie prefiksy się nakładają — dict eliminuje fall-through, więc najpierw potwierdzić kontraktem, że każdy `command` jest dokładnie jeden.

---

## 6. Otwarte Pytania

1. **Widoczność repo i PII.** `CLAUDE.md` (commitowany na GitHub) zawiera numer telefonu i adres e-mail allowlisty oraz aliasy/ścieżki infrastruktury. Czy `Acoste616/AIagent` jest prywatne? Jeśli kiedykolwiek ma być publiczne — te dane muszą wyjść z historii gita, nie tylko z HEAD.
2. **AUTO_APPLY: usunąć czy obwarować?** Zadanie 1.3 wymaga Twojej decyzji o wizji autonomii: czy „pełna autonomia napraw" jest celem wartym ryzyka S1, czy wystarcza `/approve` (obecny default)?
3. **Horyzont życia stanu.** Jak długo system ma działać bez interwencji? Odpowiedź kalibruje retencję (2.1): 90 dni jak koszty, czy inne okno dla konwersacji/audit?
4. **Bash w self-repair (1.4).** Czy akceptujesz spadek skuteczności napraw w zamian za twarde ograniczenie Bash do pytest? Alternatywa: zostawić, ale nigdy nie włączać AUTO_APPLY.
5. **Kandydaci do deprecjacji.** `CONFIG_REFERENCE.md` wykazuje 124 jednorazowe env vars — czy chcesz przeglądu „które flagi L4.x są martwe po zmianie kursu na iMessage-primary", czy deprecjonować tylko przy okazji?
6. **Cel wydajnościowy.** Jaka jest akceptowalna latencja odpowiedzi czatu (dziś dominuje czas CLI Claude, sekundy)? To decyduje, czy P2/P3 są warte ruchu teraz, czy dopiero przy realnym wzroście plików.

---

*Audyt wykonany bez modyfikacji kodu. Wszystkie numery linii odnoszą się do working tree na `0cc60cc` (L4.102).*
