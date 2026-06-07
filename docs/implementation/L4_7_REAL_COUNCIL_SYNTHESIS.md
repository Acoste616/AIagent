# L4.7 Real Council Host Synthesis

## Cel

AI Council nie może zwracać stałej decyzji niezależnie od głosów operatorów. L4.7 dodaje warstwę hosta-sędziego, która rozstrzyga głosy Claude, Grok i Codex, a wynik trafia do krótkiego summary Telegrama.

## Co działa

- `/council` nadal uruchamia trzy role:
  - Claude: propozycja planu,
  - Grok: research/red-team,
  - Codex: feasibility i minimalny patch.
- Host synthesis próbuje uzyskać od Groka ścisły JSON z decyzją, faktami, sporem, next actions i pytaniem do Bartka.
- Jeśli JSON nie wróci albo model jest niedostępny, fallback wyciąga decyzję, fakty i spór z realnych linii operatorów.
- Raport taska pokazuje `Synthesis source`, więc widać czy decyzja pochodzi z `llm_host`, `fallback` czy `fallback_no_json`.
- Stały Telegram listener ma teraz lock `state/telegram_listener.lock`, żeby druga instancja nie powodowała `telegram_getUpdates http_409`.

## Dlaczego to było potrzebne

Po L4.6 system miał już Front Brain i pamięć rozmowy, ale structured Council nadal było za bardzo szablonowe. To powodowało odpowiedzi podobne do zwykłego bota, nie do Poke-like operatora, który rozumie kontekst i wybiera następny ruch.

Drugim realnym problemem były konflikty `http_409` w Telegram polling. To oznacza, że Telegram widział więcej niż jeden proces pobierający wiadomości. L4.7 blokuje równoległy stały listener, więc Scheduled Task i fallback startup nie powinny rywalizować o update'y.

## Granice

To nie jest jeszcze pełne Poke parity. Nadal brakuje:

- proaktywnych watchers i nudges,
- realnych integracji read-only/write z Gmail, Calendar, Drive, GitHub,
- pełnego execution loop z verifierem i rollbackiem,
- streaming/progress na poziomie rozmowy,
- iPhone capture i iMessage bridge.

L4.7 zamyka brak w Council decision layer i przygotowuje grunt pod kolejne sprinty.
