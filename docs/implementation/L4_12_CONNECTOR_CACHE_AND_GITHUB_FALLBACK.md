# L4.12 Connector Cache and GitHub Fallback

Cel: przybliżyć AI Council do Poke-level integracji bez czekania na pełny OAuth. System ma umieć indeksować lokalne export/cache źródła i dawać source-backed wyniki nawet wtedy, gdy natywny connector wymaga jeszcze logowania.

## Co wdrożono

- `connector_index.sqlite` w `state/` jako read-only cache index.
- `/connector ingest <name>` dla `gmail`, `calendar`, `drive`.
- `/source search gmail|calendar|drive <query>` najpierw szuka w indeksie, potem w folderze export/cache.
- `/connectors` pokazuje `indexed=N` i status `indexed`, jeśli cache istnieje bez aktywnego OAuth.
- GitHub search po nieudanym `gh auth` próbuje publiczny fallback przez GitHub Search API dla `AI_COUNCIL_GITHUB_REPO`.
- `/goal`, `/status`, `/capabilities` pokazują L4.12 i następny brak: real OAuth bridge.

## Komendy

- `/connectors`
- `/connector auth github`
- `/connector ingest gmail`
- `/connector brief gmail faktura`
- `/source search github connector`

## Bezpieczeństwo

- Tylko read-only.
- Brak zapisu do Gmail/Calendar/Drive/GitHub.
- Brak tokenów w Telegramie.
- Publiczny GitHub fallback nie zastępuje `gh auth` dla prywatnych zasobów.

## Ograniczenia

- Gmail/Calendar/Drive nadal wymagają export/cache albo przyszłego OAuth sync.
- GitHub public fallback działa tylko dla publicznie dostępnych danych.
- Full Poke-level integrations dalej wymagają real OAuth bridge oraz approval flow dla write/send/schedule.

## Następny sprint

L4.13 Real OAuth Bridge:

- Gmail read/search sync,
- Calendar read sync,
- Drive/Docs read/search sync,
- GitHub CLI auth fix dla prywatnych repo/issues/PR,
- source labels i artifacts dla każdej odpowiedzi,
- write/send/schedule dopiero po Risk Officer.

## Testy

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m unittest tests/test_ai_council.py`
- `git diff --check`
