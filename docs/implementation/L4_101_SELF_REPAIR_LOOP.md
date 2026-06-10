# L4.101 — Self-Repair Loop

Data: 2026-06-10. Domyka drugą połowę pętli błędów z L4.55/L4.100: system nie tylko wykrywa i diagnozuje błędy, ale sam produkuje ZWERYFIKOWANY patch i czeka na jedno słowo zgody.

## Pipeline

1. **Kandydat** — `self_repair_candidates()`: grupuje `errors.jsonl` (okno `AI_COUNCIL_SELF_REPAIR_WINDOW_DAYS`, default 2 dni) po `context`, rankuje po liczności, pomija severity=info i konteksty próbowane w ostatnich 3 dniach (`state/self_repair.jsonl` — anty-pętla).
2. **Diagnoza** — `claude_self_repair_response()`: Claude CLI (subskrypcja, bez tools), prompt = kontrakt patcha + błąd (message/traceback) + fragment źródła wokół `record_error("<context>"`. Koszt przez `reserve_operator_call`. Model może odmówić: `NO_SAFE_PATCH <powód>`.
3. **Format patcha** — bloki `PATCH_FILE:` + `<<<<FIND/====/>>>>`; parser (`parse_repair_blocks`) wymusza: allowlistę plików (`AI_COUNCIL_SELF_REPAIR_FILES`, default `ai_council.py,tests/`; zero traversal — walidacja `..`/absolutnych PRZED normalizacją), max `AI_COUNCIL_SELF_REPAIR_MAX_BLOCKS` (6), FIND unikalny w pliku (dokładnie 1 wystąpienie — `apply_repair_blocks`).
4. **Izolowana weryfikacja** — `prepare_repair_workspace()` kopiuje `ai_council.py` + `tests/` + `pyproject.toml` do `state/self_repair/<id>/work/`; `verify_repair_workspace()` odpala `py_compile` + PEŁNY `pytest -q tests` z przekierowanymi katalogami zapisu (patch-kandydat nigdy nie dotyka produkcyjnego stanu). Czerwone = koniec, wpis `verify_failed`.
5. **Propozycja** — zielone ⇒ `create_action(type="self_repair", risk="R2")` z blokami i dowodem („N passed"); powiadomienie przez `deliver_proactive` (iMessage primary). **Nic nie dotyka produkcji.**
6. **`/approve <act-id>`** — `execute_self_repair_action()`: backup dotykanych plików do `state/self_repair/<id>/backup/`, aplikacja bloków na `PROJECT_DIR`, `py_compile` po patchu (czerwony ⇒ automatyczny rollback z backupu + status failed). Po sukcesie: wymagany restart listenera (komunikat w wyniku).
7. **Rollback** — `self-repair-undo --id <repair-id>` (CLI) przywraca pliki z backupu w każdej chwili.

## Wejścia

- CLI: `python ai_council.py self-repair [--send]`, `self-repair-undo --id <id>`
- Telegram/iMessage: `/self-repair` (tło — w `BACKGROUND_COMMANDS`), naturalnie: „samonaprawa", „napraw się sam", „self repair"
- Harmonogram: `recipes/self_repair_loop.json` — codziennie 21:30 (30 min po wieczornym audycie błędów, który zasila errors/improvements)

## Bezpieczniki

Produkcja zmienia się WYŁĄCZNIE przez `/approve` (R2); allowlista plików + brak traversal; limit bloków; pełny pytest przed propozycją; backup + auto-rollback przy czerwonym `py_compile`; anty-pętla na kontekstach; `control_paused_reason("model")` i budżety operatorów respektowane; flaga główna `AI_COUNCIL_SELF_REPAIR` (default true — bo sama propozycja jest read-only).

## Weryfikacja

Mac: 540 passed (15 nowych w `tests/test_self_repair.py`: parser/allowlista/unikalność FIND, kandydaci+anty-pętla, happy-path bez dotykania produkcji, czerwona weryfikacja blokuje propozycję, NO_SAFE_PATCH, approve+backup+undo, auto-rollback po złym patchu, PRAWDZIWY izolowany pytest na mini-projekcie, routing slash/naturalny/background, recipe loadable). Ruff czysty.

## L4.102 — pełne narzędzia w sandboxie + opcjonalna autonomia

Na życzenie Bartka model naprawczy dostał **pełne narzędzia plikowe (Read/Write/Edit/Bash)**, ale wyłącznie wewnątrz izolowanej kopii roboczej:

- `AI_COUNCIL_SELF_REPAIR_TOOLS=true` (default): zamiast zgadywać FIND/REPLACE z fragmentu, Claude jest odpalany z `--permission-mode bypassPermissions`, cwd = `state/self_repair/<id>/work/` (kopia `ai_council.py` + `tests/` + `pyproject.toml`). Czyta cały plik, edytuje bezpośrednio, może sam odpalić `pytest` Bashem. Obok trzymana jest nietknięta kopia `pristine/`; `self_repair_changeset()` liczy różnicę i zwraca pełną nową treść każdego ZMIENIONEGO pliku z allowlisty. Zmiana pliku spoza allowlisty albo nowy plik poza `tests/` ⇒ odrzucenie, zero akcji.
- Tryb blocks (L4.101) został jako fallback (`AI_COUNCIL_SELF_REPAIR_TOOLS=false`) — `execute_self_repair_action` obsługuje oba kształty payloadu (`changeset` po treści / `blocks` FIND-REPLACE).
- **`AI_COUNCIL_SELF_REPAIR_AUTO_APPLY`** (default false): gdy ON, ZIELONY (pełny pytest) patch jest stosowany do produkcji od razu — nadal z backupem, `py_compile` po patchu i auto-rollbackiem przy czerwonym. To jest „pełna autonomia na jeden przełącznik". Domyślnie OFF: produkcja czeka na `/approve`.
- Undo radzi sobie z nowo utworzonymi przez model plikami testowymi (marker `.absent` ⇒ `self-repair-undo` je kasuje, nie przywraca pustych).

Niezmienne bezpieczniki nawet przy pełnych narzędziach: edycje tylko w sandboxie, allowlista plików egzekwowana na diffie, pełne 548 testów przed jakimkolwiek dotknięciem produkcji, backup + auto-rollback, `self-repair-undo`.

## Świadome ograniczenia v1

Jeden kandydat na cykl; tylko edycje istniejących plików (nowe testy przez kotwicę FIND); patch produkcyjny weryfikowany `py_compile` (pełny pytest był zielony na identycznej kopii — różnice tylko gdy produkcja dryfuje od kopii w czasie approval); restart listenera ręczny/przez schtasks po approve.
