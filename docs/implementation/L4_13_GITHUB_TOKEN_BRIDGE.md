# L4.13 GitHub Token Bridge

Cel: dać AI Council realną read-only ścieżkę do GitHuba nawet wtedy, gdy `gh auth` na desktopie jest nieważny. To przybliża system do Poke-level integracji bez proszenia o sekret w Telegramie.

## Co wdrożono

- `github_source_search()` próbuje kolejno:
  1. `gh issue list`, jeśli `gh auth status` działa,
  2. GitHub Search API z `GITHUB_TOKEN` albo `GH_TOKEN`,
  3. publiczny GitHub Search API fallback.
- `/connectors` pokazuje `github | token_present`, jeśli token jest dostępny, ale nie obiecuje poprawności tokena przed wykonaniem searchu.
- `/source search github <query>` używa tokena read-only, gdy CLI auth jest zepsuty.
- Token nie jest wypisywany w odpowiedziach Telegrama.
- Błędny token `401/403` nie jest maskowany publicznym fallbackiem, bo wtedy użytkownik mógłby myśleć, że czyta prywatne źródła.

## Konfiguracja

Token ustaw tylko w `.env` albo system environment:

```text
GITHUB_TOKEN=...
```

albo:

```text
GH_TOKEN=...
```

Nie wklejaj tokena w Telegram.

## Bezpieczeństwo

- Bridge jest read-only.
- Nie dodaje issue, PR, komentarzy ani pushy.
- Write actions zostają za Risk Officer i explicit approval.
- Token jest maskowany przez istniejące redaction rules.

## Ograniczenia

- `GITHUB_TOKEN/GH_TOKEN` nie naprawia natywnego `gh auth`; to osobna ścieżka API.
- Publiczny fallback działa tylko dla publicznych zasobów.
- Prywatne repo/issues/PR wymagają tokena z odpowiednimi read permissions.

## Następny sprint

L4.14 Google OAuth Bridge:

- Gmail read/search sync,
- Calendar read sync,
- Drive/Docs read/search sync,
- source-backed artifacts,
- write/send/schedule dopiero po Risk Officer.

## Testy

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m unittest tests/test_ai_council.py`
- `git diff --check`
