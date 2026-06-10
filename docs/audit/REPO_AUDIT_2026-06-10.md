# Audyt repozytorium AIagent — 2026-06-10

Audytor: Claude (Cowork). Zakres: pełne repo na stanie commita `1f11d01` (L4.99) + lokalne niezacommitowane zmiany. Żaden kod nie został zmodyfikowany. Wszystkie numery linii zweryfikowane na lokalnym checkoutcie Mac.

---

## 1. Streszczenie Wykonawcze

Ocena ogólna: **B-**. Jak na prywatny, jednoosobowy system budowany iteracyjnie przez LLM, repo jest w zaskakująco dobrym stanie operacyjnym: bezpieczeństwo jest solidne (hmac.compare_digest, zero `shell=True`, parametryzowany SQL, redakcja sekretów, wielowarstwowa obrona path traversal), testów jest 497 i przechodzą, dokumentacja warstw jest wzorowa. Główny dług to **architektura**: `ai_council.py` ma 18 375 linii i 736 funkcji w jednym pliku, router intencji to 652-liniowa funkcja z 67 gałęziami if/elif, a każda warstwa L4.xx powiększa monolit i dodaje kolejne flagi env (już ~158). Trzy największe ryzyka: (1) brak jakiegokolwiek CI — jedyną bramką jest dyscyplina ręcznego `pytest` przed deployem; (2) nieograniczony wzrost plików JSONL czytanych w całości na gorącej ścieżce każdej wiadomości (`costs.jsonl` już 464 KB po kilku dniach); (3) dryf trzech środowisk (repo Mac / `D:\ai-council` / most w `~/.ai_council` poza repo), który już raz doprowadził do sytuacji „produkcja przed repo" (merge Conversation Brain w L4.97). Trzy największe okazje: CI w pół godziny pracy daje stałą siatkę bezpieczeństwa; cache/rotacja ledgera kosztów usuwa jedyne realne wąskie gardło wydajności; tablica dispatch dla routera zatrzyma erozję najbardziej krytycznej funkcji systemu zanim stanie się nieedytowalna.

---

## 2. Mapa Repo

**Cel projektu.** Prywatny „Agent OS" Bartka — klon Poke z ambicją przewyższenia go (OpenClaw/Hermes-style lokalna egzekucja). Telegram-first asystent z mostem iMessage, pamięcią SQLite, akcjami za approvalem i `/undo`, kosztami w ledgerze. Docelowy użytkownik: jedna osoba (Bartek). Poziom dojrzałości: zaawansowany prototyp produkcyjny dla jednego użytkownika — działa w produkcji na Windows (`D:\ai-council`), ale bez infrastruktury zespołowej (CI, code review poza audytami Codex/Claude).

**Stack.** Python ≥3.10, **wyłącznie stdlib** (świadoma decyzja — zero requirements.txt, zero zewnętrznych zależności; import-listę potwierdza analiza AST: argparse, sqlite3, subprocess, urllib, http, threading itd.). Testy: unittest uruchamiane przez pytest. Deploy: PowerShell przez SSH (Tailscale). Operatorzy LLM przez subprocess do CLI `claude`/`codex` i HTTP do xAI.

**Punkty wejścia i przepływ.**
- `ai_council.py:18259` — `main()`, tryby CLI (`listen`, `respond`, `respond-b64`, `doctor`, ...).
- Przepływ wiadomości Telegram: `listen_once` (`ai_council.py:17944`, polling getUpdates) → `route_text` (`:15551`) → `natural_intent_route` (`:14474`) → `build_response` (`:17529`) → wysyłka.
- Przepływ iMessage: most na Macu (`scripts/mac_imessage_bridge_standalone.py`) → SSH na Windows → `respond_b64_reply` (`ai_council.py:17811`).
- HTTP serwer dla iPhone Shortcuts: `ShortcutRequestHandler` (`ai_council.py:4206`), bind 127.0.0.1, token przez `hmac.compare_digest`.

**Katalogi.**

| Ścieżka | Opis |
|---|---|
| `ai_council.py` | Cały runtime: 18 375 linii, 736 funkcji, 4 klasy, 898 instrukcji top-level |
| `tests/test_ai_council.py` | 9 413 linii, 497 testów w ~30 klasach unittest, 1 021 użyć mock/patch |
| `tests/conftest.py` | Hermetyzacja sesji testowej (przekierowanie STATE_DIR itd.) — bardzo dobra |
| `docs/` | 122 pliki: implementation per warstwa L4.xx, handoffs, research, agent-loop |
| `scripts/` | Most iMessage (×2 warianty), research Grok, deploy Windows (PowerShell) |
| `recipes/` | 11 definicji JSON cyklicznych zadań |
| `windows-deploy/` | Skrypty start/stop/status produkcji |
| `state/`, `logs/`, `errors/`, `artifacts/` | Runtime, poprawnie w `.gitignore`, nic wrażliwego nie jest trackowane (zweryfikowane `git ls-files`) |

**Zaskoczenia.**
- Brak `.github/workflows` — żadnego CI mimo 497 testów i dyscypliny deployowej opisanej w CLAUDE.md.
- `git status` brudny: 8 zmodyfikowanych, niezacommitowanych plików (`docs/research/*`, `scripts/windows/*.ps1`).
- Dwa mosty iMessage w repo (`mac_imessage_bridge.py` 117 linii vs `_standalone.py` 300 linii), a produkcyjny działa z trzeciej kopii w `~/.ai_council/` poza repo.
- `read_jsonl_tail` (`ai_council.py:691-692`) czyta **cały plik** i tnie końcówkę — nazwa obiecuje tail, implementacja nie.
- Konwencje istniejące (warte zachowania): warstwy L4.xx z dokiem per warstwa, helpery `cfg()/bool_cfg()/int_cfg()`, sanityzacja audytu, snapshot przed zapisem + `/undo`.

---

## 3. Raport Audytu

Legenda: [F] fakt zweryfikowany w kodzie, [O] ocena/osąd. Ciężkość: K/W/Ś/N.

### 3.1 Architektura i projektowanie

**A1. [F][W] Monolit-bóg: `ai_council.py` = 18 375 linii, 736 funkcji, 4 klasy.**
Gdzie: cały plik. Dlaczego to ważne: każda warstwa L4.xx edytuje ten sam plik; konflikt Mac↔Windows w L4.97 (niezmergowany Conversation Brain na produkcji) był bezpośrednim skutkiem — nie da się robić częściowych diffów modułów, tylko diff całego świata. Czas ładowania kontekstu przez LLM-buildera rośnie z każdą warstwą, a ryzyko przypadkowej regresji w odległym miejscu pliku rośnie razem z nim.

**A2. [F][W] `natural_intent_route` — 652 linie, 67 gałęzi if/elif, zero dispatch table.**
Gdzie: `ai_council.py:14474-15125`. Dlaczego: to najbardziej krytyczna funkcja systemu (każda wiadomość przez nią przechodzi) i jednocześnie najtrudniejsza do bezpiecznej edycji. Kolejność gałęzi jest semantyką — wstawienie nowego intentu w złym miejscu po cichu przechwytuje cudze frazy. Brak rejestru/tabeli (predykat → handler) oznacza, że nie da się testować intentów w izolacji od kolejności.

**A3. [F][Ś] 32+ stałych ścieżek zamrażanych w czasie importu** (`STATE_DIR`, `COSTS_FILE`, `OFFSET_FILE` — `ai_council.py:55` i okolice). Dlaczego: docstring `tests/conftest.py` wprost opisuje incydent, w którym testy z produkcyjnego checkoutu pisały do żywego `state/costs.jsonl`. Obejście (env przed importem) działa, ale to symptom: konfiguracja powinna być rozwiązywana w czasie wywołania, nie importu.

**A4. [F][Ś] Eksplozja konfiguracji: ~158 zmiennych `AI_COUNCIL_*`.**
Gdzie: cały plik; dostęp przez helpery `cfg()/bool_cfg()` (dobre), ale flagi tylko przybywają. Dlaczego: nikt nie wycofuje flag po ustabilizowaniu warstwy; macierz możliwych konfiguracji jest nietestowalna; `conftest.py` musi ręcznie zerować 14 flag, żeby suite był deterministyczny.

**A5. [O][Ś] Trzy środowiska bez jednego źródła prawdy: repo Mac, `D:\ai-council`, `~/.ai_council/imessage_bridge.py`.** Most produkcyjny żyje poza repo (potwierdza handoff `docs/handoffs/SESSION_HANDOFF_2026-06-10.md`); w repo są dwa jego warianty (`scripts/mac_imessage_bridge.py`, `scripts/mac_imessage_bridge_standalone.py`). CLAUDE.md sam ostrzega „Windows may be ahead of Mac — diff first". To proces generujący incydenty klasy L4.97.

### 3.2 Jakość kodu

**Q1. [F][Ś] Połknięte wyjątki w ścieżkach krytycznych — 30 bloków `except Exception`, z czego 17 gołych.**
Najgroźniejsze:
- `ai_council.py:668-674` — `append_jsonl`: przy timeout locka wpis idzie do sidecara, ale jeśli i sidecar rzuci `OSError`, wpis **ledgera kosztów ginie bez śladu** (`pass`). Budżet operatorów liczy się z tego pliku.
- `ai_council.py:7516-7517` — migracje SQLite `except sqlite3.Error: pass`: nieudany `ALTER TABLE` jest niewidzialny; kolejne zapytania do brakującej kolumny wybuchną daleko od przyczyny.
- `ai_council.py:8771-8774` — `project_memory_context_for_prompt` zwraca `""` przy dowolnym błędzie: operator po cichu traci kontekst pamięci i nikt się nie dowie.

**Q2. [F][Ś] Duplikacja media-capture: `capture_telegram_media_message` (`:3649`, 100 linii) vs `capture_shortcut_media_payload` (`:3976`, 104 linie)** — ok. 70% wspólnej logiki (STT, limity rozmiaru, routing intencji media). Poprawka w jednej ścieżce nie trafia do drugiej.

**Q3. [F][N] f-string w SQL: `conn.execute(f"ALTER TABLE memory_entries ADD COLUMN {col_ddl}")` (`ai_council.py:7515`).** Wartości są hardcoded (lista literałów dwie linie wyżej), więc nie jest to dziś exploitowalne — ale to jedyny niesparametryzowany SQL w pliku i zły wzorzec do kopiowania.

**Q4. [F][N] `read_jsonl_tail` (`:691-692`) to fałszywy tail** — `read_jsonl(path)[-limit:]` czyta cały plik. Mylące API; patrz też P1.

### 3.3 Bezpieczeństwo

Stan ogólny: **dobry** — to najmocniejszy wymiar repo. Zweryfikowane pozytywy: token Shortcuts porównywany przez `hmac.compare_digest`; bind na 127.0.0.1 z limitem body; **zero** `shell=True` w całym pliku; SQL parametryzowany (poza Q3); redakcja sekretów w logach/errors; allowlist Telegram egzekwowana na wejściu handlera; wielowarstwowa obrona path-traversal w zapisach workspace (containment + symlinki + re-weryfikacja); TLS i timeouty na wywołaniach sieciowych; `git ls-files` nie zawiera żadnego pliku stanu/sekretu; `.gitignore` poprawny.

**S1. [F][Ś] `respond_b64_reply` (`ai_council.py:17811-17825`) nie weryfikuje nadawcy.** Funkcja przyjmuje dowolny tekst i wykonuje pełny pipeline (routing, pamięć, auto-fact-capture) z `chat_id` ustawionym na zaufany `TELEGRAM_ALLOWED_CHAT_ID`. Jedyną bramką jest most na Macu, który czyta wątki self-chat. Konsekwencja: każdy, kto dostanie się do SSH/maszyny Mac albo zmodyfikuje most, ma pełny kanał do systemu z uprawnieniami Bartka — brak defense-in-depth (np. HMAC podpisu od mosta albo parametru sender weryfikowanego po stronie Windows).

**S2. [F][N] Auto-fact-capture z iMessage (`:17824`) zapisuje fakty do pamięci bez approvala** — w połączeniu z S1 to wektor zatrucia pamięci (memory poisoning) z niezweryfikowanego kanału. Mitygacja: kwarantanna faktów już istnieje (komentarz w kodzie), więc ciężkość N.

### 3.4 Testowanie

**T1. [F][Ś] Brak CI.** `.github/workflows` nie istnieje. 497 testów przechodzi tylko wtedy, gdy ktoś pamięta je uruchomić; commit `927ce03` (naprawa hermetyczności testów względem live Claude CLI) pokazuje, że suite bywał zależny od środowiska i nikt by tego nie wyłapał automatycznie.

**T2. [F][Ś] Jeden plik testowy 9 413 linii** (`tests/test_ai_council.py`, ~30 klas). Działa, ale czas nawigacji rośnie, a kolizje przy równoległej pracy (Claude + Codex worker) są gwarantowane.

**T3. [O][Ś] 1 021 użyć mock/patch na 497 testów** — testy są mocno przyspawane do wewnętrznych nazw funkcji monolitu. Każdy refaktoring (np. A2) będzie wymagał masowych poprawek mocków; to testy „wykonania", nie tylko zachowania. Łagodzi to fakt, że spora część klas (RoutingTests, HandsSandboxTests, WorkspaceActionRollbackTests) testuje realne zachowanie na plikach tmp.

**T4. [F][N] Pozytyw: `tests/conftest.py` to wzorowa hermetyzacja** (sandbox per sesja, zerowanie flag i sekretów) — zachować.

### 3.5 Wydajność

**P1. [F][W] O(n) odczyt rosnących plików na gorącej ścieżce.**
- `usage_today` (`ai_council.py:4703-4708`) czyta **cały** `costs.jsonl` i filtruje po dniu; wołane z `reserve_operator_call` (`:4719`) i guardów budżetu (`:4922`, `:4946`, `:5118`, `:5130`, `:5150`) — czyli przy praktycznie każdym wywołaniu operatora.
- `get_latest_task` (`:1477`) buduje dict z **całego** `tasks.jsonl` per lookup.
- `costs.jsonl` ma 464 KB po ~4 dniach produkcji; brak jakiejkolwiek rotacji/retencji. Za pół roku to dziesiątki MB parsowane JSON-linia-po-linii przy każdej wiadomości — system będzie wyraźnie zwalniał, a winowajca będzie nieoczywisty.

**P2. [O][N] Polling Telegram + brak cache w pamięci** — akceptowalne dla jednego użytkownika; nie ruszać.

### 3.6 Zależności

Zdrowe. Zero zewnętrznych pakietów (stdlib-only — zweryfikowane AST), więc brak CVE, locków i ryzyk licencyjnych. Jedyna „zależność" to zewnętrzne CLI (`claude`, `codex`) i API xAI — wersjonowane poza repo, sprawdzane przez `doctor`.

### 3.7 DevEx i operacje

**D1. [F][W] = T1.** Brak CI to także brak bramki lint: `ruff` jest skonfigurowany (`pyproject.toml:6-7`), ale nigdzie nie wymuszany.

**D2. [F][Ś] Brudny working tree na Macu**: 8 zmodyfikowanych plików niezacommitowanych (`docs/research/*` ×5, `scripts/windows/*.ps1` ×3). Przy zadeklarowanym ryzyku „Windows ahead of Mac" każdy niezacommitowany plik to przyszły konflikt merge.

**D3. [O][N] Pozytyw: dyscyplina operacyjna ponadprzeciętna** — backup przed deployem (`D:\ai-council\backups\pre-L4.97`), smoke testy po deployu, `doctor`, ledger kosztów, dokument loop per deploy.

### 3.8 Dokumentacja

**Doc1. [F][N] README nieaktualny w 2 miejscach**: komenda testów `python -X utf8 tests/test_ai_council.py` (uruchamia unittest bez conftest — bez hermetyzacji! prawidłowa komenda z CLAUDE.md to `python3 -m pytest -q tests/test_ai_council.py`); sekcja „GitHub Auth Status" opisuje zepsuty push, a push działa (10 commitów z ostatniej sesji). Konsekwencja pierwszego: ktoś uruchomi testy z produkcyjnego checkoutu i zapisze śmieci do żywego stanu — dokładnie incydent, przed którym broni conftest.

**Doc2. [O] Pozytyw: 122 pliki docs z konwencją per-warstwa i handoffami** — to realna przewaga tego repo; utrzymać.

### 3.9 Mocne strony (podsumowanie)

Bezpieczeństwo na poziomie przemyślanym (sekcja 3.3), snapshot+`/undo` przed zapisami, approval-gating akcji R1, ledger kosztów z rezerwacjami, atomic write offsetu Telegram (`:13802-13805`, tmp + `os.replace` — poprawny wzorzec), hermetyczny conftest, stdlib-only, dokumentacja i dyscyplina deployowa. To wszystko należy chronić podczas refaktoringu, nie „poprawiać".

---

## 4. Strategia Poprawy

### Temat 1: Brak automatycznej siatki bezpieczeństwa (wyjaśnia T1, D1, część D2)
Stan docelowy: każdy push na GitHub przechodzi `ruff check` + `pytest` w GitHub Actions; deploy na Windows tylko z zielonego maina. Zasada: dyscyplina ręczna już istnieje — zautomatyzowanie jej kosztuje godziny, a eliminuje całą klasę regresji. „Zrobione" = CI failuje na czerwonych testach i błędach ruff; badge w README.

### Temat 2: Monolit eroduje w tempie warstwy dziennie (wyjaśnia A1, A2, Q2, T2)
Stan docelowy (skalibrowany do projektu, NIE enterprise): `ai_council.py` zostaje plikiem głównym, ale (a) router intencji przechodzi na tablicę dispatch (lista reguł: predykat → handler, kolejność jawna), (b) nowe warstwy dodają handlery zamiast gałęzi if/elif, (c) duplikaty media-capture zlewają się do wspólnego rdzenia. Zasada: nie przepisujemy działającego systemu; zatrzymujemy mechanizm, który go psuje. „Zrobione" = `natural_intent_route` < 150 linii, intenty rejestrowane deklaratywnie, 497+ testów zielonych bez zmiany semantyki.

### Temat 3: Dane rosną bez granic, hot path czyta wszystko (wyjaśnia P1, Q4)
Stan docelowy: ledger kosztów dzielony per dzień (`costs-YYYY-MM-DD.jsonl`) albo cache'owany w pamięci procesu listenera; `tasks.jsonl` z indeksem ostatnich wpisów; polityka retencji (np. 90 dni) dla JSONL. „Zrobione" = `usage_today` nie czyta więcej niż 1 dzień danych; rozmiar `state/` ograniczony retencją.

### Temat 4: Awarie są ciche tam, gdzie powinny krzyczeć (wyjaśnia Q1)
Stan docelowy: polityka „połknięcie wyjątku zawsze zostawia ślad" — każdy `except: pass` w ścieżce ledgera, migracji i pamięci loguje do `errors.jsonl` (mechanizm już istnieje). „Zrobione" = zero gołych `pass` w ścieżkach: koszty, migracje, snapshoty, wysyłka.

### Temat 5: Trzy środowiska, brak jednego źródła prawdy (wyjaśnia A5, D2, S1)
Stan docelowy: most iMessage żyje w repo jako jeden plik (standalone), deploy do `~/.ai_council` jest skryptem; brudne pliki zacommitowane lub odrzucone; `respond_b64_reply` dostaje weryfikację nadawcy (parametr sender + allowlist po stronie Windows). „Zrobione" = `diff` repo↔produkcja czysty na obu maszynach; jeden plik mostu.

### Czego świadomie NIE naprawiać
- **Nie wprowadzać frameworków/zależności** (LangChain, FastAPI, pydantic) — stdlib-only to realny atut operacyjny (deploy = kopia pliku) i decyzja właściciela.
- **Nie rozbijać monolitu na pełny pakiet modułów teraz** — wysiłek XL, wysokie ryzyko regresji przy 1 021 mockach przyspawanych do nazw; tablica dispatch daje 80% korzyści za 20% kosztu. Pełna modularyzacja dopiero, gdy dispatch się przyjmie.
- **Nie naprawiać P2 (polling, brak cache poza hot-path)** — jeden użytkownik, zysk pomijalny.
- **Nie budować observability klasy enterprise** — `errors.jsonl` + `doctor` + loop-docs wystarczą.
- **Q3 (f-string SQL)** — naprawić przy okazji najbliższej edycji tego fragmentu, nie jako osobne zadanie.

---

## 5. Plan Zadań

### Kamień milowy 0 — Sieć bezpieczeństwa

| # | Zadanie | Pliki | Kryteria akceptacji | Wysiłek | Ryzyko | Zależy od |
|---|---|---|---|---|---|---|
| 0.1 | **CI: GitHub Actions** — workflow `python -m pytest -q tests/test_ai_council.py` + `ruff check ai_council.py` na push/PR do main, Ubuntu + Windows runner (produkcja jest na Windows) | `.github/workflows/ci.yml` | Push z czerwonym testem failuje; badge w README | **S** | Zerowe (nie dotyka runtime) | — |
| 0.2 | **Commit/triage brudnych plików** — przejrzeć 8 zmodyfikowanych plików (`docs/research/*`, `scripts/windows/*.ps1`), zacommitować lub `git restore` | wg `git status` | `git status --short` pusty na Macu | **S** | Niskie | — |
| 0.3 | **Golden-path testy routingu jako kontrakt** — tabelaryczny test: lista (wiadomość → oczekiwany route-type) dla ~40 reprezentatywnych fraz pokrywających wszystkie 67 gałęzi `natural_intent_route`; to siatka pod refaktor 2.1 | `tests/test_ai_council.py` (lub nowy `tests/test_routing_contract.py`) | Każda gałąź `natural_intent_route` ma ≥1 przypadek; test niezależny od kolejności wewnętrznych wywołań (bez mocków wewnętrznych) | **M** | Zerowe | — |

### Kamień milowy 1 — Krytyczne poprawki (poprawność i bezpieczeństwo)

| # | Zadanie | Pliki | Kryteria akceptacji | Wysiłek | Ryzyko | Zależy od |
|---|---|---|---|---|---|---|
| 1.1 | **Weryfikacja nadawcy w `respond_b64_reply`** — most przekazuje sender handle; Windows sprawdza go względem `AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS`; brak/obcy sender → odmowa + wpis w errors | `ai_council.py:17811`, `scripts/mac_imessage_bridge_standalone.py` | Test: obcy sender nie wykonuje routingu ani fact-capture; smoke iMessage działa | **M** | Średnie (zmiana protokołu most↔Windows; wymaga zgranego deployu obu stron) | 0.1 |
| 1.2 | **Ciche awarie → errors.jsonl** — `append_jsonl` sidecar-OSError (`:673`), migracje SQLite (`:7516`), `project_memory_context` (`:8773`) i pozostałe gołe `pass` z listy Q1 logują przez istniejący mechanizm error-store (z guardem przeciw rekursji: błąd zapisu errors nie może wołać errors) | `ai_council.py` | grep `except.*:\n\s*pass` w ścieżkach kosztów/migracji/pamięci = 0; test wymusza OSError i sprawdza wpis | **M** | Niskie | 0.1 |
| 1.3 | **Ledger kosztów: plik per dzień + retencja** — `record_operator_usage` pisze do `costs-YYYY-MM-DD.jsonl`; `usage_today` czyta tylko plik dnia; migracja: stary `costs.jsonl` czytany jako fallback dla dni historycznych; retencja 90 dni w `doctor` lub recipe | `ai_council.py:4665-5150` | `usage_today` nie otwiera plików spoza bieżącego dnia; testy budżetu zielone; rozmiar czytany per wiadomość = O(1 dzień) | **M** | Średnie (budżety/guardy liczą z tego pliku — pomyłka = przepalenie budżetu lub fałszywa blokada) | 0.1, 0.3 |

### Kamień milowy 2 — Wysoka dźwignia

| # | Zadanie | Pliki | Kryteria akceptacji | Wysiłek | Ryzyko | Zależy od |
|---|---|---|---|---|---|---|
| 2.1 | **Tablica dispatch dla `natural_intent_route`** — rejestr `INTENT_RULES: list[(name, predicate, handler, priority)]`; gałęzie przenoszone partiami po ~10 z zachowaniem kolejności; funkcja główna iteruje po rejestrze | `ai_council.py:14474-15125` | 497+ testów + golden-path (0.3) zielone po każdej partii; `natural_intent_route` <150 linii; nowy intent = dodanie wpisu, nie edycja funkcji | **XL → rozbić na 6-7 partii L** | Wysokie łącznie, niskie per partia (testy 0.3 są siatką) | 0.3 |
| 2.2 | **Unifikacja media-capture** — wspólny rdzeń `capture_media_core()` z parametrami źródła; obie funkcje (`:3649`, `:3976`) stają się cienkimi adapterami | `ai_council.py` | Testy media zielone; logika STT/limitów istnieje w jednym miejscu | **M** | Średnie | 0.1 |
| 2.3 | **Most iMessage: jedno źródło prawdy** — usunąć `scripts/mac_imessage_bridge.py` (117 linii), `_standalone.py` jest kanoniczne; skrypt `scripts/deploy/install_imessage_bridge.sh` kopiuje do `~/.ai_council` i restartuje LaunchAgent; diff repo↔`~/.ai_council` czysty | `scripts/` | Produkcyjny most == plik w repo (diff pusty); instalacja jedną komendą | **S** | Niskie | 1.1 |
| 2.4 | **`read_jsonl_tail` naprawdę tail** — czytanie od końca pliku (seek + bloki) albo zmiana nazwy na uczciwą; przegląd wywołań `read_jsonl` na rosnących plikach (`tasks.jsonl` — `get_latest_task:1477`) | `ai_council.py:677-700, 1475-1482` | Brak pełnego odczytu rosnących plików w hot-path; testy zielone | **M** | Niskie | 1.3 |

### Kamień milowy 3 — Jakość i dopracowanie

| # | Zadanie | Pliki | Kryteria akceptacji | Wysiłek | Ryzyko | Zależy od |
|---|---|---|---|---|---|---|
| 3.1 | **README fix** — poprawna komenda testów (pytest!), usunięcie nieaktualnej sekcji GitHub Auth, badge CI | `README.md` | Komendy z README działają 1:1 | **S** | Zerowe | 0.1 |
| 3.2 | **Inwentaryzacja flag env** — wygenerować listę ~158 `AI_COUNCIL_*` z miejscem użycia i defaultem do `docs/operations/CONFIG_REFERENCE.md`; oznaczyć kandydatów do usunięcia (flagi warstw ustabilizowanych) | `docs/operations/` | Dokument kompletny; ≥10 flag oznaczonych do deprecjacji z decyzją Bartka | **M** | Zerowe (sam dokument) | — |
| 3.3 | **Split pliku testów** — podział `test_ai_council.py` na ~6 plików per domena (routing, hands, memory, costs, imessage, operators), conftest bez zmian | `tests/` | pytest zbiera ≥497 testów; CI zielone | **M** | Niskie | 0.1 |
| 3.4 | **Retencja pozostałych JSONL** — `actions.jsonl`, `errors.jsonl`, `progress_events.jsonl`: rotacja/archiwizacja w `doctor` lub recipe | `ai_council.py`, `recipes/` | `state/` nie rośnie bez ograniczeń; archiwa w `state/archive/` | **S** | Niskie | 1.3 |

### Szybkie wygrane (do zrobienia od razu, niezależnie)
1. **0.1 CI** — największy stosunek zysku do wysiłku w całym planie.
2. **0.2 commit brudnych plików** — 15 minut, usuwa ryzyko konfliktu.
3. **3.1 README fix** — zła komenda testów to realna pułapka (uruchamia suite bez hermetyzacji conftest).
4. **2.3 jeden most iMessage** — mały, zamyka dryf środowisk.

### Szkice implementacji — top 3

**0.1 CI.** `.github/workflows/ci.yml`: matrix `{ubuntu-latest, windows-latest}`, Python 3.10; kroki: checkout → setup-python → `pip install pytest ruff` → `ruff check ai_council.py tests/` → `python -m pytest -q tests/test_ai_council.py`. Pułapki: (a) testy muszą być hermetyczne bez sieci/CLI — commit `927ce03` sugeruje, że już są, ale runner Windows to zweryfikuje brutalnie; pierwszy run potraktować jako diagnozę, flaky testy naprawić zamiast wyłączać; (b) `ruff` na 18k-liniowym pliku zgłosi zaległości — zacząć od `ruff check --select E9,F63,F7,F82` (same błędy krytyczne) i zaostrzać.

**1.3 Ledger per dzień.** Krok 1: `costs_file_for_day(day)` zwraca `STATE_DIR/costs-{day}.jsonl`; `record_operator_usage` pisze tam (append_jsonl bez zmian). Krok 2: `usage_today` czyta plik dnia + (przejściowo) filtruje stary `costs.jsonl` po `day` tylko jeśli plik dnia nie istnieje — usuwa to ryzyko podwójnego liczenia. Krok 3: testy L2LedgerTests przejrzeć pod kątem ścieżek pliku (conftest przekierowuje STATE_DIR, więc większość przejdzie bez zmian). Pułapka: `collapse_usage_events`/rezerwacje (`:4719`) zakładają, że rezerwacja i rozliczenie są w tym samym pliku — deploy o północy może rozciąć parę; rozwiązanie: dzień brany z rezerwacji, nie z zegara rozliczenia.

**2.1 Dispatch table.** Krok 1: zdefiniować `IntentRule = (name, match_fn, handler_fn)` i `INTENT_RULES: list` nad `natural_intent_route`; funkcja najpierw iteruje po regułach, potem spada do starego bloku if/elif (strangler pattern). Krok 2: przenosić gałęzie od góry funkcji (kolejność = priorytet) partiami po ~10, po każdej partii pełny pytest + golden-path 0.3. Krok 3: po przeniesieniu wszystkich — stary blok znika. Pułapki: (a) gałęzie współdzielą lokalne zmienne pomocnicze (znormalizowany tekst, flagi) — przekazywać jeden obiekt `ctx` zamiast rozplatać; (b) część gałęzi ma side-effecty przed `return` — przenosić 1:1, bez „poprawiania przy okazji"; (c) mocki w testach celują w nazwy handlerów — zachować nazwy funkcji handlerów.

---

## 6. Otwarte Pytania do Bartka

1. **Skala docelowa**: czy system na zawsze pozostaje jednoosobowy? Jeśli kiedyś multi-user, S1/A3 rosną do ciężkości Wysokiej i modularyzacja przestaje być opcjonalna.
2. **Deploy jako kopia jednego pliku**: czy `D:\ai-council` zakłada, że runtime to dosłownie jeden `ai_council.py`? To determinuje, czy pełna modularyzacja (pakiet) jest w ogóle na stole, czy zostajemy przy dispatch-table wewnątrz pliku.
3. **Retencja danych**: ile dni historii kosztów/akcji/błędów chcesz trzymać (propozycja: 90)? Czy `state/hands_backups` (444 KB) ma politykę czyszczenia?
4. **Deprecjacja mostów**: potwierdzenie, że `scripts/mac_imessage_bridge.py` (117 linii) jest martwy i kanoniczny jest `_standalone.py`.
5. **Stan Windows vs Mac**: przed M1 potrzebny `diff` repo↔`D:\ai-council` (CLAUDE.md ostrzega, że Windows bywa przed Makiem) — czy zlecasz to jako pierwszy krok?
6. **Flagi do wycofania**: które warstwy uznajesz za ustabilizowane na stałe (kandydaci do usunięcia ich flag w 3.2)?

---

*Metodologia: pełna analiza AST `ai_council.py`, grep-audyt wzorców (subprocess, SQL, except, sekrety), `git ls-files`/`git status`, lektura kluczowych ścieżek (routing, ledger, HTTP handler, iMessage relay, append_jsonl, conftest), dwa niezależne przebiegi agentów (bezpieczeństwo, architektura) z ręczną weryfikacją cytowanych linii. Lżejszy przegląd: `recipes/*.json`, skrypty PowerShell, treść `docs/research` (zweryfikowano tylko spójność z kodem, nie merytorykę). Twierdzenia agentów, których nie potwierdziłem osobiście, zostały pominięte lub skorygowane (np. rzekomy race na OFFSET_FILE — zapis jest atomowy: `ai_council.py:13802-13805`).*
