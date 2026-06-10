# L4.103 — Audit Remediation Loop (Sprinty A–D)

Stan: **Mac worktree, NIE wdrożone na produkcję** (`D:\ai-council` czeka na zgodę Bartka).
Pętla operacyjna: audyt (REPO_AUDIT v2) → council/decyzje (AUDIT_ADDENDUM) → implementacja (ten dok) → weryfikacja (pytest/ruff/py_compile) → deploy *gated*.

Wejście: `docs/audit/REPO_AUDIT_2026-06-10_v2_CLAUDE_FULL.md` + decyzje Bartka (`docs/audit/AUDIT_ADDENDUM_DECISIONS_2026-06-10.md`).
Weryfikacja: **575 testów zielonych** (z 548 baseline; +27 nowych, −3 martwe funkcje), **ruff czysty** (rozszerzony zestaw reguł), **py_compile OK**, **coverage 76%** (`ai_council.py`).

## Decyzje Bartka odwzorowane w kodzie

1. Repo prywatne — bez czyszczenia PII.
2. **Pełna autonomia napraw** — AUTO_APPLY zostaje, ale obwarowany strażnikami.
3. **Praca 24/7** — retencja/odczyt od ogona pod nieograniczony czas życia.
4. **Bash w self-repair zostaje pełny** (naprawia też skrypty) — hartowane środowisko, nie kastracja.
5. **Przegląd deprecjacji** — wykonany.
6. **Widoczność „że działa, pisze"** — W1 + W4 wdrożone.

## Sprint A — fundament + szybkie wygrane

- **W1 typing (decyzja 6)**: `telegram_send_typing` + `TelegramTypingPulse` (daemon-thread, best-effort, nigdy nie rzuca). `listen_once` owija synchroniczne `build_response` pulsem „pisze…" gdy `send=True`. Testy: `tests/test_visibility.py`.
- **Sanityzacja mostu (audit 1.2, High)**: `scripts/mac_imessage_bridge_standalone.py` — `_safe_msg_id` (`[A-Za-z0-9._:-]{1,64}`), `_safe_status` (tylko `sent|failed`), `_safe_host_token` (blokuje metaznaki w `HOST_DIR/HOST_PY/ALIAS`). `ack()` odmawia egzekucji przy niebezpiecznych wartościach. Zamyka wstrzyknięcie do zdalnego PowerShella. Testy: `tests/test_imessage_bridge_script.py` (pierwsze testy mostu w ogóle).
- **ruff select (audit 2.5)**: `pyproject.toml` → `select = [E,F,B,UP,SIM,C4,PIE]` z punktowymi `ignore` dla czysto stylistycznych reguł (świadomie, bez churn 40 miejsc w monolicie). Naprawiony B904 w `safe_resolve`. Autofix UP012 w paru miejscach.
- **coverage (audit 0.1)** + **matryca Pythona (audit 2.6/D1)**: CI instaluje `pytest-cov`, raportuje `--cov`, testuje na **3.10 i 3.12** × ubuntu/windows.
- **dead-code sweep (decyzja 5, częściowo)**: usunięte 3 funkcje z zerem referencji (`source_status`, `verify_action`, `council_response`). Reszta listy z audytu okazała się **żywa** (referencje w testach/kodzie) — `llm_route`, `mail_send`, `imessage_*` ZOSTAJĄ; audyt podagenta zawyżył listę martwych.
- **higiena**: `.gitignore` += `**/.DS_Store`, `.coverage*`, `htmlcov/`.

## Sprint B — bezpieczeństwo autonomii

- **Strażnicy AUTO_APPLY (decyzja 2)**: `self_repair_guard_auto_apply(workdir, baseline)` blokuje auto-apply gdy patch (a) zmienia ciało dowolnej funkcji z `SELF_REPAIR_PROTECTED_FUNCS` (allowlist/auth/approval/redaction/self-repair — porównanie AST, sama lista też chroniona) lub (b) przekracza `AI_COUNCIL_SELF_REPAIR_MAX_DIFF_LINES` (default 400). Plus **adwersarialny recenzent** `self_repair_adversarial_review` (drugie, niezależne wywołanie Claude; REJECT/awaria → degradacja do `/approve`). Każdy blok → `auto_apply_blocked` + wiadomość z `/approve`. Testy: `tests/test_self_repair.py` (+6).
- **Hartowanie Bash (decyzja 4)**: `self_repair_env()` — pełny Bash zostaje, ale środowisko bez sekretów (`TOKEN/KEY/SECRET/PASSWORD` + `TELEGRAM_/XAI_/GROK_/GITHUB_/GH_/GOOGLE_`) i `AI_COUNCIL_ENV` wskazujący nieistniejącą ścieżkę. Użyte w `claude_self_repair_tools_run`.
- **Fail-closed iMessage (audit 1.1, High)**: `imessage_sender_allowed` — pusty allowlist **DENY** (`denied_no_allowlist`); migracyjny opt-in `AI_COUNCIL_IMESSAGE_ALLOW_OPEN=true` → `open_explicit`. `doctor` raportuje stan allowlisty (OK/OPEN/FAIL-CLOSED). Testy: `tests/test_channel_policy.py`; zaktualizowane testy zależne od starego trybu open.
- **Cisza → dowód (audit Q1, 1.5)**: trzy najgorsze `except Exception: pass` dostały `record_error` — drop audit w ścieżce hands (`hands_audit_drop`), drop tury konwersacji (`conversation_turn_drop`), drop order_handoff (`order_handoff_drop`).

## Sprint C — życie 24/7 + widoczność

- **Odczyt od ogona (audit P1, High)**: `recent_conversation` przepisane na `iter_jsonl_reverse` z early-stop (było: pełny `read_jsonl` przy każdej wiadomości; `CONVERSATIONS_FILE` rośnie bez końca). Testy: `tests/test_visibility.py::RecentConversationTailTests`.
- **W4 „co robisz?" (decyzja 6)**: nowa komenda `/working` + `live_status_response()` — lista zadań w toku z czasem trwania, ostatnim etapem progress, oznaczeniem utkniętych. Reguła naturalna („co robisz", „nad czym pracujesz", „czym się zajmujesz", …) w `_nat_status_diagnostics`. Helper `_fmt_elapsed`. Testy: `tests/test_visibility.py::LiveStatusW4Tests`.
- **W5 watchdog**: pokryty istniejącym `stuck_tasks_monitor` (recipe) + `detect_proactive_events` + nowe powierzchnia `/working`.
- **Testy charakterystyczne listen_once (audit 0.2)**: pusta paczka = no-op (zero turów, brak offsetu); poprawne przesunięcie offsetu o `update_id+1`. `tests/test_council_memory_state.py`.

## Sprint D — szwy monolitu (świadomie ograniczony)

Zgodnie z zatwierdzoną strategią (AUDIT_ADDENDUM, Temat 4: *granice przez rejestry, NIE pełna modularizacja teraz*), pełny rewrite `build_response`/`route_text` na rejestr jest **odłożony** (XL, wysokie ryzyko deploy/self-repair, mały zysk dziś).

- Wykonano bezpieczną, mechaniczną ekstrakcję `@all` z `build_response` → `all_council_response(prompt, task_id)` (audit A2 hotspot). Zachowanie 1:1, golden routing contract zielony bez zmian.
- `3.2` (scalenie „duplikatów subprocess Claude") **anulowane** — funkcje wskazane przez audyt (`brain_claude_response`, `run_operator_subprocess`) **nie istnieją**; to była halucynacja podagenta. Realne funkcje (`claude_response`, `claude_flow_response`, `poke_chat_claude_response`, self-repair) są różne, nie ma czego scalać.

## Nowe zmienne środowiskowe (L4.103)

| Zmienna | Default | Rola |
|---|---|---|
| `AI_COUNCIL_IMESSAGE_ALLOW_OPEN` | `false` | migracyjny opt-in trybu otwartego iMessage (fail-closed bypass) |
| `AI_COUNCIL_SELF_REPAIR_MAX_DIFF_LINES` | `400` | limit rozmiaru diffu dla auto-apply |
| `AI_COUNCIL_SELF_REPAIR_ADVERSARIAL` | `true` | włącza recenzenta bezpieczeństwa przed auto-apply |

## Co zostało celowo poza zakresem (do przyszłych pętli)

- W2 (iMessage ACK-first), W3 (heartbeat etapowy frontu) — wymagają zmian w żywej ścieżce kanałowej; bezpieczniejsze do wdrożenia z dostępem do produkcji.
- Pełny rejestr `build_response`/`route_text` (2.2/2.3) — odłożone strategicznie.
- Retencja/sharding `NUDGES/IMPROVEMENTS/AUDIT` (P3) i `latest_by_id` (P2) — niższy priorytet niż konwersacje.
- Kasacja żywego-ale-martwego `llm_route` (9 ref. testowych) — wymaga usunięcia dedykowanej klasy testów; osobny commit.

## Weryfikacja (do powtórzenia przed deploy)

```bash
PYTHONPYCACHEPREFIX=/tmp/pc python3 -m py_compile ai_council.py
python3 -m ruff check ai_council.py tests scripts
COVERAGE_FILE=/tmp/.cov python3 -m pytest -q tests --cov=ai_council --cov-report=term
```

Wynik na Macu: 575 passed, ruff All checks passed, coverage 76%.

## Uwaga operacyjna

W sandboxie audytu pozostał `.git/index.lock` (po wcześniejszym crashu narzędzia git) — usuń go na Macu (`rm .git/index.lock`) przed pierwszym commitem. `docs/.DS_Store` wciąż jest w indeksie — `git rm --cached docs/.DS_Store` (gitignore już go łapie na przyszłość).
