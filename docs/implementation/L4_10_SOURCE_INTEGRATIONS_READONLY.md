# L4.10 Source Integrations Read-only

Cel: AI Council ma jasno pokazywać, z jakich źródeł umie korzystać teraz, które są tylko gotowe do podłączenia, i nie udawać pełnego Poke-level OAuth bez realnej autoryzacji na desktop runtime.

## Co wdrożono

- `/sources` pokazuje status źródeł w trybie read-only.
- `/source search <name> <query>` przeszukuje dostępne lokalne źródła i zwraca nazwę źródła oraz krótki snippet.
- Naturalne intencje działają bez slashy:
  - `pokaż źródła`
  - `szukaj w źródłach memory Poke`
  - frustracja typu `nie odpowiada jak Poke / gdzie cel` kieruje do `/goal`.
- `/goal`, `/status` i `/capabilities` pokazują aktualny cel, gotowe elementy i brakujące integracje.

## Źródła

- `memory`: SQLite AI Council memory, dostępne od razu.
- `artifacts`: lokalne task artifacts, reports i Claude collaboration outputs.
- `openclaw`: lokalny eksport OpenClaw, jeśli `OPENCLAW_EXPORT` istnieje.
- `github`: GitHub CLI read-only, wymaga poprawnego `gh auth`.
- `gmail`: read-only export albo przyszły OAuth bridge.
- `calendar`: read-only export albo przyszły OAuth bridge.
- `drive`: read-only export albo przyszły OAuth bridge.

## Ograniczenia

- To nie jest jeszcze pełny Poke-level connector layer.
- Gmail, Calendar i Drive nie mają jeszcze desktop OAuth bridge.
- GitHub działa tylko wtedy, gdy `gh auth status` przechodzi na desktopie.
- Write/send/schedule dalej wymagają Risk Officer i approval.
- Wyszukiwanie lokalne ma limit plików, żeby Telegram nie zawieszał się na dużych katalogach.

## Następny sprint

L4.11 OAuth/Connector Bridge:

- naprawić desktop GitHub auth,
- dodać Gmail read/search bridge,
- dodać Calendar read bridge,
- dodać Drive/Docs read bridge,
- każda odpowiedź źródłowa ma zawierać artifact i source label,
- write/send/schedule dopiero po explicit approval.

## Testy

- `python3 -m py_compile ai_council.py tests/test_ai_council.py`
- `python3 -m unittest tests/test_ai_council.py`
- `git diff --check`
