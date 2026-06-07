# L4.11 Connector Bridge Read-only

Cel: zbliżyć AI Council do Poke-level integracji przez jawny connector layer. System ma pokazywać, co jest gotowe, co wymaga auth/config, jak to podłączyć i tworzyć source-backed raporty z dostępnych źródeł.

## Co wdrożono

- `/connectors` pokazuje gotowość connectorów.
- `/connector check <name>` pokazuje status, tryb, search readiness i szczegóły źródła.
- `/connector auth <name>` pokazuje bezpieczne kroki logowania lub konfiguracji bez proszenia o tokeny w Telegramie.
- `/connector brief <name> <query>` tworzy raport w `reports/connector-brief-...md` na bazie dostępnych źródeł.
- Naturalne intencje bez slashy:
  - `pokaż konektory`
  - `sprawdź connector github`
  - `podłącz github`
- `/goal`, `/status` i `/capabilities` pokazują L4.11 oraz następny realny brak: OAuth bridge.

## Connector status

- `memory`: lokalne read-only search.
- `artifacts`: lokalne read-only search po artifacts/reports/Claude collab.
- `openclaw`: lokalne read-only search po `OPENCLAW_EXPORT`.
- `github`: GitHub CLI read-only, wymaga poprawnego `gh auth`.
- `gmail`: export/cache folder albo przyszły OAuth bridge.
- `calendar`: export/cache folder albo przyszły OAuth bridge.
- `drive`: export/cache folder albo przyszły OAuth bridge.

## Domyślne foldery export/cache

Domyślne foldery są liczone względem `PROJECT_DIR`:

- `<PROJECT_DIR>\sources\gmail`
- `<PROJECT_DIR>\sources\calendar`
- `<PROJECT_DIR>\sources\drive`

Na desktop runtime oznacza to obecnie:

- `D:\ai-council\sources\gmail`
- `D:\ai-council\sources\calendar`
- `D:\ai-council\sources\drive`

Można też ustawić:

- `AI_COUNCIL_GMAIL_EXPORT_DIR`
- `AI_COUNCIL_CALENDAR_EXPORT_DIR`
- `AI_COUNCIL_DRIVE_EXPORT_DIR`

## Granice bezpieczeństwa

- L4.11 jest read-only.
- Write/send/schedule zostaje za Risk Officer i explicit approval.
- Tokenów nie wkleja się w Telegram.
- GitHub auth ma iść przez natywne `gh auth login`.

## Następny sprint

L4.12 Real OAuth Bridge:

- naprawić `gh auth` na desktopie,
- dodać read/search bridge Gmail,
- dodać read bridge Calendar,
- dodać read/search bridge Drive/Docs,
- każdy wynik ma mieć source label i artifact,
- external write dopiero po Risk Officer.

## Testy

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m unittest tests/test_ai_council.py`
- `git diff --check`
