# L4.75 — GitHub Actions v2 (deeper integration)

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: LANDED + DEPLOYED + LIVE (381 passed).
Zamyka część luki "integration breadth" z audytu Poke — **autonomicznie** (token GitHub już działał, bez nowego auth).

## Co robi
- `/gh issues [filtr]` — listuje otwarte issues (read), filtruje PR-y, opcjonalny filtr po tytule.
- `/gh issue <tytuł> | <opis>` — tworzy realne issue (gated: PROVIDER_WRITE_ENABLED + GITHUB_ISSUE_WRITE_ENABLED, oba ON).
- `/gh comment <numer> <treść>` — komentuje issue (gated).
- Naturalnie: „pokaż issues" → list; „stwórz issue: X" → create.
- Helpery: `gh_api` (Bearer token), `gh_repo`, `gh_write_enabled`, `gh_list_issues`/`gh_create_issue`/`gh_comment_issue`. Audyt per write.

## Tests (GitHubActionsTests, 5)
list filtruje PR-y (key-presence, nie truthiness), empty, create gated-off, create-when-enabled, routing (/gh + naturalne).

## Verification
- Mac + Windows: **381 passed**.
- Live: `/gh issues` → „Brak otwartych issues"; „stwórz issue: … | auto-close" → realne issue #2 utworzone → zamknięte.

## Uwaga
Read (list) działa zawsze (token). Write (create/comment) gated flagami (ON na hoście). `/gh` jest explicit-only (poza LLM-router allowlist) — bezpieczne.
