# L4.104 — DeepAgents Adapter

Data: 2026-06-10.

## Decyzja

`langchain-ai/deepagents` został dodany jako **opcjonalny, ręczny adapter**, nie
jako nowy core AI Council.

Powód: obecny runtime ma już własny router, pamięć SQLite, approval gates,
koszt ledger, self-repair sandbox i operatorów Claude/Codex/Grok. DeepAgents
jest wartościowe do eksperymentów z dłuższymi taskami, ale wciągnięcie go jako
domyślnej orkiestracji byłoby migracją architektury.

## Wejście

- Komenda: `/deepagent <prompt>`
- Status: `/deepagent status`
- Health: `/health` pokazuje `deepagent: L4.104:<state>`
- Opcjonalna instalacja: `python -m pip install -r requirements-deepagents.txt`

## Flagi

- `AI_COUNCIL_DEEPAGENT_ENABLED=false` — domyślnie off.
- `AI_COUNCIL_DEEPAGENT_MODEL=` — model LangChain z tool calling, np. ustawiany
  dopiero po dobraniu providera i credentials.
- `AI_COUNCIL_DEEPAGENT_DAILY_CALL_LIMIT` — dzienny limit wywołań operatora.
- `AI_COUNCIL_DEEPAGENT_ESTIMATED_COST_USD` — szacunek do cost ledger.

## Bezpieczeństwo

- Import `deepagents` jest leniwy; brak pakietu nie psuje startu.
- Pierwsza wersja nie przekazuje custom tools.
- Built-in filesystem DeepAgents jest blokowany regułą deny-all permissions.
- Komenda nie jest domyślnie background jobem i nie zastępuje `/delegate`.
- Wdrożenia kodu dalej idą przez Grok/Claude/Codex worker + host audit.

## Weryfikacja

- Testy adaptera mockują runtime; bez sieci, bez provider credentials.
- Core pozostaje stdlib-only dopóki operator nie zostanie jawnie doinstalowany i
  włączony flagą.
