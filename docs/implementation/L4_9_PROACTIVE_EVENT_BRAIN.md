# L4.9 Proactive Event Brain

## Cel

AI Council ma zacząć działać bardziej jak Poke/OpenClaw delivery layer: nie tylko odpowiadać na komendy, ale samemu wykrywać ważne sygnały i dostarczać je jako nudge.

## Co działa

- Nowa komenda `/nudges`.
- Naturalne intencje:
  - `pokaż nudges`,
  - `pokaż proaktywne`,
  - `proaktywne sygnały`.
- Proactive Event Brain wykrywa:
  - błędy z ostatnich 24h,
  - stuck background tasks,
  - pending actions starsze niż próg nudge,
  - Grok cost/call threshold.
- Każdy event dostaje `nudge_key`, więc ten sam sygnał nie spamuje Telegrama.
- Stała pętla `serve` i bounded `listen` uruchamiają scan obok scheduler recipes.

## Granice

- To jest read-only detection + local state write.
- Brak shell execute.
- Brak external write.
- Brak Gmail/Calendar/Drive/GitHub read jeszcze w tym sprincie.
- Nie ma pełnego “agent sam wykonuje wszystko”; nudge kieruje do `/approve`, `/deny`, `/errors`, `/status`, `/cost` lub `/nudges`.

## Dlaczego to zbliża do Poke

Poke-like UX to nie tylko czat, ale delivery: system przypomina o ważnych rzeczach i prowadzi użytkownika do kolejnego kroku. L4.9 tworzy pierwszą centralną skrzynkę proaktywnych sygnałów.

## Następny sprint

L4.10 Source Integrations Read-only:

- Gmail read/search,
- Calendar read,
- Drive/Docs read,
- GitHub read,
- każde źródło z nazwą źródła w artifact,
- write/send/schedule dopiero po Risk Officer i approval.

