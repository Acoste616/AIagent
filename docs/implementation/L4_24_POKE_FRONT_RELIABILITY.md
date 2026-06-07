# L4.24 Poke Front Reliability

Cel: gdy Bartek pisze normalnie albo pyta czemu bot milczy, Telegram front ma odpowiadać lokalnie, szybko i diagnostycznie, bez przepalania Groka.

## Zmiany

- Dodano `/front`.
- Naturalne frazy typu `front status`, `czemu bot nie odpowiada`, `dlaczego nie odpowiada` routują do `/front`.
- `/front` pokazuje:
  - ostatni Telegram update z audit loga,
  - offset i PID listenera,
  - liczbę wysłanych, nieudanych i dry odpowiedzi,
  - stan kill/pause/model routera,
  - dzisiejsze użycie i blokady Groka,
  - błędy z ostatnich 24h.
- Krótki chat jest local-first i nie wywołuje Groka dla wiadomości typu `Hej`, `co dalej`, `działasz`, `status`, `front`, `goal`, `nie odpowiada`.
- Grok chat nadal może działać dla dłuższych, wartościowych odpowiedzi, ale jest bramkowany przez `poke_chat_should_use_llm()`.
- `/health`, `/selftest`, `/goal`, `/capabilities` raportują L4.24.

## Efekt

To zamyka konkretną lukę z poprzedniego zachowania: zwykłe wiadomości mogły zużywać Groka, a po limicie front wyglądał jak słaby fallback. Teraz krótkie i diagnostyczne wiadomości mają odpowiedź lokalną, a `/front` mówi czy problem jest przed botem, w wysyłce Telegrama, czy w modelach.

## Weryfikacja

- Routing naturalny do `/front`.
- `/front` działa bez sieci na podstawie audit loga.
- Krótki chat nie wywołuje `request_json`.
- Mac: `python3 -m py_compile ai_council.py && python3 -m unittest tests.test_ai_council` -> `163/163 OK`.
- Windows Desktop: `py -3 -m py_compile .\ai_council.py; py -3 -m unittest tests.test_ai_council` -> `163/163 OK`.

## Nadal Brakuje

- Token-level albo bogatszy progress dla długich model calls.
- iPhone Shortcuts jako główne wejście.
- Prywatny iMessage bridge po stabilnym Telegram core.
- Write-capable connectors po Risk Officer i approval.
