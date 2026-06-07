# L4.23 Cost Ledger Reservation

Cel: zatrzymać przepalanie limitów modeli i poprawić Poke-like niezawodność frontu.

## Zmiany

- Dodano `COST_LOCK_FILE` i blokadę plikową dla rezerwacji kosztu.
- `reserve_operator_call()` zapisuje `reserved` przed drogim wywołaniem modelu.
- `finalize_operator_call()` zapisuje wynik końcowy z tym samym `usage_id`.
- `usage_today()` logicznie zwija `reserved -> completed/failed/timeout/missing`, więc koszt nie liczy się podwójnie.
- Grok, Grok X research, vision/STT, Codex, Claude i Claude Flow używają rezerwacji przed callami.
- LLM router jest domyślnie wyłączony dla zwykłego chatu, żeby nie zużywał Groka na każdą wiadomość.
- Front fallback ma konkretną odpowiedź dla `co dalej` i skarg o Poke parity.
- Blokady zachowują źródło i powód, np. `poke_chat: model calls paused`.

## Efekt

System nadal nie jest pełnym Poke. L4.23 zamyka lukę kosztowo-niezawodnościową, która powodowała, że zwykłe rozmowy i routing mogły wyczerpać Groka, a potem front zachowywał się jak słaby fallback.

## Weryfikacja

- `python3 -m py_compile ai_council.py`
- `python3 -m unittest tests.test_ai_council`
- Testy rezerwacji: drugi call blokuje się już po pierwszym `reserved`.
- Testy finalizacji: `reserved -> completed` liczy się jako jeden call.

## Znane ograniczenie

Jeśli proces padnie między `reserved` i finalnym statusem, rezerwacja zostaje w ledgerze do końca dnia i może nadmiernie blokować kolejne calle. To jest fail-safe: lepiej zablokować niż przekroczyć limit. Następna iteracja może dodać TTL/reconciliation dla osieroconych rezerwacji.
