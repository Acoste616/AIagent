# L4.8 Goal Status Surface

## Cel

Bot ma umieć pokazać aktualny cel systemu i lukę do Poke parity bez uruchamiania długiego modelu. To odpowiada na sytuacje, gdy Bartek pyta naturalnie: "gdzie ten cel" albo "czemu to nie odpowiada jak Poke".

## Co działa

- Nowa komenda `/goal`.
- Naturalne routing phrases:
  - `gdzie ten cel`,
  - `nie odpowiada jak Poke`,
  - `brakuje do Poke`,
  - `poke parity`,
  - `poke-like`.
- `/goal` pokazuje:
  - że goal nie jest ukończony,
  - co już działa,
  - czego brakuje do Poke-level,
  - bieżące ryzyka,
  - następny sprint.

## Następny sprint

L4.8 wskazuje następny realny blok: Proactive Event Brain, czyli watchers -> nudge -> council -> approval -> wykonanie.

