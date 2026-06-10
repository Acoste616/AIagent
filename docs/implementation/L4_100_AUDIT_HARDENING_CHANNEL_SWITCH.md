# L4.100 — Audit hardening + przełączenie kanału głównego na iMessage

Data: 2026-06-10. Źródło wymagań: `docs/audit/REPO_AUDIT_2026-06-10.md` (plan M0–M3) + decyzja Bartka: główny kanał iMessage przez numer telefonu, Telegram jako fallback. Wykonane w jednej pętli (Claude primary builder), commit-per-zadanie, Mac NIE-zdeployowane na Windows.

## Co się zmieniło

### M0 — sieć bezpieczeństwa
- **CI**: `.github/workflows/ci.yml` — ruff + py_compile + pytest na push/PR, matrix ubuntu+windows, Python 3.10. Ruff: cały plik doprowadzony do zera findingów (4 trywialne naprawione).
- **Kontrakt routingu**: `tests/test_routing_contract.py` — 67 fraz golden-path (mode+command+priorytet gałęzi). To siatka pod refaktor dispatch.
- Working tree wyczyszczony (8 plików miało tylko zmianę trybu 644→755 — przywrócone).

### M1 — poprawność i bezpieczeństwo
- **1.2 Ciche awarie zostawiają ślad**: `append_jsonl` — przy podwójnej awarii (lock timeout + sidecar OSError) wiersz idzie do `<plik>.dropped.jsonl` + licznik `APPEND_JSONL_DROPS`; reconcile scala też `.dropped` i ma ochronę przed DUPLIKACJĄ wierszy ledgera, gdy unlink sidecara się nie powiedzie (truncate zamiast ponownego scalenia). Migracje sqlite (`_migrate_memory_columns`) i `project_memory_context_for_prompt` raportują przez `record_error`.
- **1.3 Ledger kosztów per dzień**: zapisy idą do `state/costs-YYYY-MM-DD.jsonl` (`costs_file_for_day`); `usage_today` czyta TYLKO plik dnia + legacy `costs.jsonl` jako fallback przejściowy (legacy first, żeby statusy z sharda wygrywały w collapse). Retencja: `prune_cost_shards` (`AI_COUNCIL_COSTS_RETENTION_DAYS`, default 90; legacy plik nigdy nie jest kasowany), odpalana lazy raz na proces.
- **1.1 Weryfikacja nadawcy iMessage (defense-in-depth)**: `respond-b64 --sender <handle>`; host normalizuje (`normalize_imessage_handle`: telefony→cyfry, maile→lowercase) i sprawdza vs `AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS`. Odmowa = pusta odpowiedź + `record_error("imessage_sender_denied")`, wiadomość NIE dotyka routingu/pamięci/faktów. Pusta allowlista = tryb legacy (filtr wątków po stronie mostu).

### Kanał: iMessage primary, Telegram fallback
- `deliver_proactive(chat_id, text, markup)` — JEDYNA polityka wyjściowa dla proaktywnych/background wiadomości:
  1. `AI_COUNCIL_IMESSAGE_PRIMARY` (default **true**) + `AI_COUNCIL_IMESSAGE_ENABLED` + outbox niezatkany → enqueue do iMessage outbox (wątek numeru telefonu = `AI_COUNCIL_IMESSAGE_TO`), Telegram milczy.
  2. Inaczej Telegram (z markup). Fallback NIE enqueue'uje (brak duplikatów po obudzeniu mostu).
  3. Tryb legacy mirror (primary=false + `AI_COUNCIL_IMESSAGE_PROACTIVE`) zachowany.
- `imessage_outbox_stale` (`AI_COUNCIL_IMESSAGE_STALE_S`, default 600 s) — wykrywa śpiący Desktop/Mac (pending starsze niż próg) i przełącza na Telegram.
- Przepięte 4 punkty wysyłki: nudge, morning brief, background fail/result. Funkcja `mirror_proactive_to_imessage` usunięta (zastąpiona polityką).
- Most (`scripts/mac_imessage_bridge_standalone.py`): przekazuje `--sender` (handle wątku, sanitizowany quote-safe) do `respond-b64`.

### M2 — dźwignia
- **2.1 Dispatch registry**: `natural_intent_route` (652 linie, 67 gałęzi) → 9-liniowy dispatcher iterujący `NATURAL_INTENT_RULE_GROUPS` = 8 uporządkowanych grup reguł (`_nat_status_diagnostics`, `_nat_ops_dashboards`, `_nat_connector_actions`, `_nat_task_lifecycle`, `_nat_memory_files_gh`, `_nat_workspace_writes`, `_nat_operator_jobs`, `_nat_research_fallthrough`). Kolejność gałęzi zachowana 1:1 (transformacja skryptowa, zero zmian semantyki — kontrakt 67 fraz zielony). Nowy intent = edycja/dodanie grupy, nie dispatchera.
- **2.2 Wspólny rdzeń media-capture**: `media_capture_analyze_and_route`, `write_media_metadata`, `media_capture_facts`, `media_capture_finalize`; capture z Telegrama i z iPhone Shortcut to cienkie adaptery (~120 zduplikowanych linii mniej).
- **2.3 Jeden most**: legacy `scripts/mac_imessage_bridge.py` + `mac_imessage_bridge_run.sh` usunięte; kanoniczny jest standalone. Installer: `scripts/deploy/install_imessage_bridge.sh` (kopia do `~/.ai_council/imessage_bridge.py`, wrapper, plist LaunchAgent, `--check` = detekcja driftu repo↔produkcja).
- **2.4 Prawdziwy tail**: `iter_jsonl_reverse` (blokowe czytanie od końca) + `read_jsonl_tail` bez parsowania całej historii; `get_latest_task` skanuje od końca (pierwsze trafienie = najnowszy wiersz).

### M3 — jakość
- **3.1 README**: pytest (z ostrzeżeniem czemu nie bezpośrednio), opis kanałów, badge CI, usunięta martwa sekcja GitHub Auth.
- **3.2** `docs/operations/CONFIG_REFERENCE.md` — 167 zmiennych env (typ, default, użycia, linia) + 124 kandydatów single-use do deprecjacji (decyzja Bartka).
- **3.3 Split testów**: `tests/test_ai_council.py` (9,4 tys. linii, 36 klas) → 6 plików domenowych `test_council_*.py` + `council_test_shared.py` (wspólny nagłówek, re-eksport przez star import). Klasy przeniesione 1:1.
- **3.4 Retencja stanu**: `rotate_state_file` (oversize → `state/archive/`), `prune_state_files` w `doctor` (progress_events, errors.jsonl, stare dzienne errors, shardy kosztów). `actions.jsonl`/`tasks.jsonl` celowo nietykane (pending approvals / historia statusów).

## Konfiguracja (nowe/zmienione)
```
AI_COUNCIL_IMESSAGE_PRIMARY=true          # iMessage jako kanał główny
AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS=      # np. +48XXXXXXXXX,me@icloud.com (HOST-side gate)
AI_COUNCIL_IMESSAGE_STALE_S=600           # failover na Telegram gdy outbox stoi
AI_COUNCIL_COSTS_RETENTION_DAYS=90        # retencja shardów kosztów
AI_COUNCIL_STATE_ROTATE_MAX_BYTES=10485760
AI_COUNCIL_ERRORS_RETENTION_DAYS=90
```

## Wymagane kroki wdrożenia (PENDING — zgoda Bartka)
1. **Numer telefonu**: wpisać do `~/.ai_council_imessage.env` na Macu (`AI_COUNCIL_IMESSAGE_TO`, `AI_COUNCIL_IMESSAGE_IDS`) i do `AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS` w `C:\Users\Komputer\.config\ai-council\.env` na Windows (te same handle!).
2. Mac: `bash scripts/deploy/install_imessage_bridge.sh` (deploy mostu z `--sender` + restart LaunchAgenta).
3. Windows: diff repo↔`D:\ai-council`, deploy, pytest, restart listenera, smoke `respond-b64 --sender`.
4. Uwaga kolejność: najpierw deploy OBU stron, potem ustawienie allowlisty (stary most bez `--sender` + ustawiona allowlista = odmowy).

## Weryfikacja
- Mac: `python3 -m pytest -q tests` → **525 passed, 180 subtests** (start sesji: 497). `ruff check ai_council.py tests scripts` → 0. Kontrakt routingu: 67 fraz.
- Windows: NIE uruchamiane (deploy za zgodą).

## Ryzyka / uwagi dla audytora (Codex)
- Refaktor 2.1 dotyka core routing → wskazany audyt Codex przed deployem (kontrakt + 525 testów zielone, transformacja była czysto mechaniczna).
- `usage_today` w dniu cutoveru liczy legacy+shard (brak podwójnego liczenia: legacy nie dostaje nowych wierszy).
- Markup Telegrama znika dla wiadomości dostarczonych przez iMessage (brak przycisków w iMessage — świadomy trade-off).
