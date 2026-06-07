# L4.14 Google OAuth Read Sync

Cel: dać AI Council Poke-like read-only kontekst z Gmaila, Kalendarza i Drive bez wysyłania maili, tworzenia wydarzeń ani edycji plików.

## Co wdrożono

- `/connector sync gmail <query>` pobiera metadane wiadomości Gmail i zapisuje je do lokalnego indeksu.
- `/connector sync calendar <query>` pobiera nadchodzące wydarzenia z Google Calendar i zapisuje je do lokalnego indeksu.
- `/connector sync drive <query>` pobiera metadane plików Google Drive i zapisuje je do lokalnego indeksu.
- `/source search gmail|calendar|drive <query>` oraz `/connector brief ...` używają potem lokalnego indeksu.
- Naturalny router rozumie wiadomości typu `sync gmail Poke`, `sync calendar spotkanie`, `sync google drive recipes`.
- `/connectors`, `/sources`, `/goal`, `/health` i `/capabilities` opisują L4.14 zamiast starego L4.13.

## Konfiguracja

Sekrety ustaw tylko w `.env` albo system environment:

```text
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
```

Nie wklejaj sekretów w Telegram.

## Bezpieczeństwo

- Bridge jest read-only.
- Gmail sync pobiera tylko metadane i snippet, nie wysyła maili.
- Calendar sync tylko czyta wydarzenia, nie tworzy i nie modyfikuje.
- Drive sync tylko czyta metadane plików, nie pobiera/edytuje treści dokumentów.
- Write/send/schedule zostają za Risk Officer i approval.
- Access token nie jest wypisywany w odpowiedziach Telegrama.

## Ograniczenia

- To nie jest jeszcze pełny Poke parity: brakuje action plannera, recipes na żywych danych, iPhone/iMessage layer i pełnego execution verifiera dla szerszych akcji.
- Drive sync v0 indeksuje metadane plików; pełne pobieranie treści Docs/Drive to kolejny sprint.
- Gmail sync v0 robi listę wiadomości i osobny read metadata per wiadomość; batchGet/większa optymalizacja to kolejny sprint.
- `AI_COUNCIL_GOOGLE_SYNC_LIMIT` jest ograniczony przez `AI_COUNCIL_GOOGLE_SYNC_LIMIT_MAX` (domyślnie 50), żeby przypadkowo nie odpalić zbyt wielu odczytów metadanych.
- OAuth refresh token musi być przygotowany poza Telegramem.

## Testy

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m unittest tests/test_ai_council.py`
- `git diff --check`
