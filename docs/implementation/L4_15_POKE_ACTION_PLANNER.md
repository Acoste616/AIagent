# L4.15 Poke Action Planner

Cel: zwykła wiadomość w Telegramu ma zostać zamieniona w konkretną kartę pracy bez wymagania slashy.

## Co wdrożono

- Naturalne wejścia typu `ogarnij mi ...`, `przygotuj mi ...`, `załatw ...`, `wyślij ...` trafiają do Action Plannera.
- Planner tworzy trwały task ze statusem `planned`.
- Karta pokazuje:
  - decyzję,
  - tryb pracy,
  - ryzyko,
  - szacowany koszt,
  - preview intencji,
  - rekomendowany route.
- `start task-...` uruchamia recommended route bez slashy.
- Side-effect requests tworzą pending action z approval, zamiast wykonywać się automatycznie.
- Pending action ma inline `Zatwierdź`, `Popraw`, `Anuluj`.

## Tryby

- `research` -> `@research`
- `flow` -> `/flow`
- `council` -> `/council`
- `recipe` -> `/recipe run project_next_action ...`
- `connector` -> `/connector brief ...`
- `approval` -> pending action, bez auto-execute

## Bezpieczeństwo

- Planner nie wykonuje external write.
- R2/R3/R4 i side-effect verbs przechodzą przez pending action.
- `start task-...` uruchamia tylko route zapisany w tasku przez planner.
- Approval dla `planner_proposal` nie wykonuje akcji automatycznie; jest zgodą/statusowym checkpointem.

## Ograniczenia

- To jest Action Planner v0, nie pełne Poke parity.
- Nie ma jeszcze automatycznego dopasowania najlepszej live recipe do każdego taska.
- Nie ma jeszcze streaming/progress UX dla samego planera.
- Poprawienie pending action jest bezpieczne: stara akcja przechodzi z `pending` do `editing`, a użytkownik pisze poprawioną intencję jako nową wiadomość.

## Testy

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m unittest tests/test_ai_council.py`
- `git diff --check`
